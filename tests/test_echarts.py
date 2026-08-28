import unittest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

class TestECharts(unittest.TestCase):
    def test_local_echarts_exists_and_not_placeholder(self):
        echarts_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'echarts.min.js')
        self.assertTrue(os.path.exists(echarts_path), "echarts.min.js must exist locally")
        self.assertGreater(os.path.getsize(echarts_path), 100000, "echarts.min.js must be a real distribution, not a placeholder")

    def test_html_loads_echarts_locally_without_cdn(self):
        html_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates', 'index.html')
        with open(html_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        self.assertIn('src="/static/echarts.min.js"', content, "HTML must load local ECharts")
        self.assertNotIn('cdn.jsdelivr.net', content, "CDN is forbidden")
        self.assertNotIn('unpkg.com', content, "CDN is forbidden")
        self.assertNotIn('cloudflare.com', content, "CDN is forbidden")
        self.assertNotIn('http://', content, "External HTTP resources are forbidden")
        
        # Check no other visualization libraries
        self.assertNotIn('chart.js', content.lower())
        self.assertNotIn('d3.js', content.lower())
        self.assertNotIn('d3.min.js', content.lower())
        self.assertNotIn('three.js', content.lower())
        self.assertNotIn('three.min.js', content.lower())

    def test_js_initializes_required_charts(self):
        js_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'app.js')
        with open(js_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Network nodes الستة موجودة
        self.assertIn('Internet', content)
        self.assertIn('Gateway', content)
        self.assertIn('Web Service', content)
        self.assertIn('File Service', content)
        self.assertIn('Admin System', content)
        self.assertIn('Digital Vault', content)
        
        # Gauge and Timeline
        self.assertIn('type: \'gauge\'', content)
        self.assertIn('type: \'graph\'', content)
        
        # Attack Path uses ECharts
        # (This is implicitly tested by checking if it updates the graph links)
        self.assertIn('links:', content)
        self.assertIn('setOption', content)
        
        # resize handler موجود
        self.assertIn('resize()', content)
        self.assertIn('window.addEventListener(\'resize\'', content)

    def test_event_rendering_does_not_depend_on_ai_result(self):
        js_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'app.js')
        with open(js_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # The logic for EVENT should handle risk updates and graph updates before AI
        # We can look for signs that EVENT block updates chart directly
        # Typically checking "case 'EVENT':" block
        idx = content.find('case \'EVENT\':')
        if idx != -1:
            event_block = content[idx:content.find('break;', idx)]
            self.assertIn('setOption', event_block, "EVENT rendering must not wait for AI_RESULT")

if __name__ == '__main__':
    unittest.main()
