import unittest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

class TestTimeline(unittest.TestCase):
    def test_timeline_echarts_initialization(self):
        js_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'app.js')
        with open(js_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        self.assertIn('timelineChart = echarts.init(timelineDom)', content, "Timeline must use ECharts")
        self.assertIn("'Discovery'", content)
        self.assertIn("'Service Probe'", content)
        self.assertIn("'Access Attempt'", content)
        self.assertIn("'Escalation'", content)
        self.assertIn("'Containment'", content)

    def test_timeline_update_logic(self):
        js_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'app.js')
        with open(js_path, 'r', encoding='utf-8') as f:
            content = f.read()

        update_idx = content.find('function updateTimeline')
        self.assertNotEqual(update_idx, -1)
        
        # ensure setOption is used instead of DOM classes
        next_func = content.find('function ', update_idx + 10)
        if next_func == -1: next_func = len(content)
        update_block = content[update_idx:next_func]
        
        self.assertIn('timelineChart.setOption', update_block, "Must update timeline using ECharts")
        self.assertNotIn('.className', update_block, "Must not use raw DOM classes for timeline anymore")
        
    def test_timeline_reset(self):
        js_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'app.js')
        with open(js_path, 'r', encoding='utf-8') as f:
            content = f.read()

        reset_idx = content.find('function handleReset')
        self.assertNotEqual(reset_idx, -1)
        next_func = content.find('function ', reset_idx + 10)
        if next_func == -1: next_func = len(content)
        reset_block = content[reset_idx:next_func]
        
        # check if it resets the timeline chart or calls updateTimeline([])
        self.assertTrue('updateTimeline([])' in reset_block or 'timelineChart.setOption' in reset_block, 
                        "Must clear the timeline chart on reset")
        
    def test_timeline_resize(self):
        js_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'app.js')
        with open(js_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        resize_idx = content.find("window.addEventListener('resize'")
        self.assertNotEqual(resize_idx, -1)
        resize_end = content.find('});', resize_idx)
        resize_block = content[resize_idx:resize_end]
        
        self.assertIn('timelineChart.resize()', resize_block, "Timeline chart must handle resize")

if __name__ == '__main__':
    unittest.main()
