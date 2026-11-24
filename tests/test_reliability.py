import hashlib
import os
from pathlib import Path
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import Mock, patch
from datetime import datetime, timedelta, timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import requests
import reliability
import prepare_model
import generate_stats as stats

SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><text>ok</text></svg>'


class ReliabilityTests(unittest.TestCase):
    def test_transient_retry_then_success(self):
        operation = Mock(side_effect=[requests.ReadTimeout(), requests.ConnectionError(), 'ok'])
        with patch('reliability.time.sleep') as sleep:
            self.assertEqual(reliability.retry_network(operation), 'ok')
        self.assertEqual(operation.call_count, 3)
        self.assertEqual(sleep.call_count, 2)

    def test_retry_exhaustion(self):
        operation = Mock(side_effect=requests.ReadTimeout())
        with patch('reliability.time.sleep'), self.assertRaises(requests.ReadTimeout):
            reliability.retry_network(operation)
        self.assertEqual(operation.call_count, 3)

    def test_permanent_http_failure_not_retried(self):
        response = Mock(status_code=401)
        operation = Mock(side_effect=requests.HTTPError(response=response))
        with self.assertRaises(requests.HTTPError):
            reliability.retry_network(operation)
        self.assertEqual(operation.call_count, 1)

    def test_rate_limit_and_server_failure_retried(self):
        for status in (429, 503):
            operation = Mock(side_effect=[requests.HTTPError(response=Mock(status_code=status)), 'ok'])
            with patch('reliability.time.sleep'):
                self.assertEqual(reliability.retry_network(operation), 'ok')

    def test_invalid_or_partial_render_preserves_every_asset(self):
        original = Path.cwd()
        with tempfile.TemporaryDirectory() as directory:
            try:
                os.chdir(directory)
                for name in ('a.svg', 'b.svg'):
                    Path(name).write_text(SVG)
                def invalid():
                    Path('a.svg').write_text(SVG.replace('ok', 'new'))
                    Path('b.svg').write_text('<broken>')
                with self.assertRaises(ET.ParseError):
                    reliability.publish_svgs(invalid, ['a.svg', 'b.svg'])
                self.assertEqual(Path('a.svg').read_text(), SVG)
                self.assertEqual(Path('b.svg').read_text(), SVG)
                self.assertFalse(list(Path('.').glob('.svg-stage-*')))
                def interrupted():
                    Path('a.svg').write_text(SVG)
                    raise RuntimeError('generation failed')
                with self.assertRaises(RuntimeError):
                    reliability.publish_svgs(interrupted, ['a.svg', 'b.svg'])
                self.assertEqual(Path('b.svg').read_text(), SVG)
            finally:
                os.chdir(original)

    def test_valid_render_published(self):
        original = Path.cwd()
        with tempfile.TemporaryDirectory() as directory:
            try:
                os.chdir(directory)
                reliability.publish_svgs(lambda: Path('a.svg').write_text(SVG), ['a.svg'])
                self.assertEqual(Path('a.svg').read_text(), SVG)
            finally:
                os.chdir(original)

    def test_verified_model_never_downloads(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'u2netp.onnx'
            path.write_bytes(b'model')
            with patch.dict(os.environ, U2NET_HOME=directory), patch.object(prepare_model, 'MODEL_MD5', hashlib.md5(b'model').hexdigest()), patch('prepare_model.requests.get') as get:
                self.assertEqual(prepare_model.prepare_model(), path)
                get.assert_not_called()

    def test_model_stream_retry_and_atomic_replacement(self):
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        # Fail after a partial chunk, then retry with a complete body.
        def broken_stream():
            yield b'partial'
            raise requests.ConnectionError()
        response.iter_content.side_effect = [broken_stream(), iter([b'model'])]
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, U2NET_HOME=directory), patch.object(prepare_model, 'MODEL_MD5', hashlib.md5(b'model').hexdigest()), patch('prepare_model.requests.get', return_value=response) as get, patch('reliability.time.sleep'):
            path = prepare_model.prepare_model()
            self.assertEqual(path.read_bytes(), b'model')
            self.assertEqual(get.call_count, 2)
            self.assertEqual(list(Path(directory).glob('*.part')), [])

    def test_bad_checksum_preserves_existing_model(self):
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.iter_content.return_value = [b'bad download']
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, U2NET_HOME=directory), patch('prepare_model.requests.get', return_value=response):
            path = Path(directory) / 'u2netp.onnx'
            path.write_bytes(b'old')
            with self.assertRaises(ValueError):
                prepare_model.prepare_model()
            self.assertEqual(path.read_bytes(), b'old')
            self.assertFalse(list(Path(directory).glob('*.part')))

    def test_no_token_or_graphql_error_is_failure(self):
        with self.assertRaises(RuntimeError):
            stats.fetch_github_data(None, 'user')
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.json.return_value = {'errors': [{'message': 'denied'}]}
        with patch('generate_stats.requests.post', return_value=response), self.assertRaises(RuntimeError):
            stats.fetch_github_data('test-token', 'user')

    def test_repository_pagination(self):
        def page(has_next, name):
            response = Mock()
            response.__enter__ = Mock(return_value=response)
            response.__exit__ = Mock(return_value=False)
            response.json.return_value = {'data': {'user': {'repositories': {
                'nodes': [{'name': name, 'languages': {'pageInfo': {'hasNextPage': False}, 'edges': []}}],
                'pageInfo': {'hasNextPage': has_next, 'endCursor': name},
            }}}}
            return response
        with patch('generate_stats.requests.post', side_effect=[page(True, 'one'), page(False, 'two')]) as post:
            data = stats.fetch_github_data('test-token', 'user')
            self.assertEqual(len(data['user']['repositories']['nodes']), 2)
            self.assertEqual(post.call_count, 2)
            self.assertEqual(post.call_args.kwargs['timeout'], (10, 90))

    def test_streaks_and_rendering(self):
        today = datetime.now(timezone.utc).date()
        days = [{'date': (today - timedelta(days=3-i)).isoformat(), 'contributionCount': n, 'color': '#0e4429'} for i, n in enumerate([2, 3, 1, 0])]
        data = {'user': {'contributionsCollection': {'contributionCalendar': {'totalContributions': 6, 'weeks': [{'contributionDays': days}]}}, 'repositories': {'nodes': [{'languages': {'edges': [{'size': 12, 'node': {'name': 'A&B', 'color': None}}]}}]}}}
        self.assertEqual(stats.streaks(data), (3, 3))
        original = Path.cwd()
        with tempfile.TemporaryDirectory() as directory:
            try:
                os.chdir(directory)
                def render():
                    stats.generate_stats_svg(data)
                    stats.generate_streak_svg(data)
                    stats.generate_langs_svg(data)
                    stats.generate_year_svg(data)
                reliability.publish_svgs(render, ['stats.svg', 'streak.svg', 'langs.svg', 'year.svg'])
                self.assertIn('3 Days', Path('streak.svg').read_text())
                self.assertIn('A&amp;B', Path('langs.svg').read_text())
                self.assertEqual(Path('year.svg').read_text().count('<title>'), 4)
            finally:
                os.chdir(original)


if __name__ == '__main__':
    unittest.main()
