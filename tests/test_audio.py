import unittest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

class TestWebAudio(unittest.TestCase):
    def test_audio_context_used(self):
        base = os.path.dirname(os.path.dirname(__file__))
        with open(os.path.join(base, "static", "app.js"), "r") as f:
            js = f.read()
            
        self.assertIn("AudioContext", js)
        self.assertIn("createOscillator", js)
        
    def test_no_external_audio_file(self):
        base = os.path.dirname(os.path.dirname(__file__))
        with open(os.path.join(base, "static", "app.js"), "r") as f:
            js = f.read()
            
        self.assertNotIn(".mp3", js)
        self.assertNotIn(".wav", js)
        self.assertNotIn("<audio", js)
        
    def test_arm_audio_exists(self):
        base = os.path.dirname(os.path.dirname(__file__))
        with open(os.path.join(base, "templates", "index.html"), "r") as f:
            html = f.read()
            
        self.assertIn("btn-arm-audio", html)
        self.assertIn("armAudio()", html)
        self.assertNotIn("autoplay", html)

if __name__ == '__main__':
    unittest.main()
