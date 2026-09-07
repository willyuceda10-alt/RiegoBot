"""Motion must be continuous while the furniture and connection indicator stay stable."""
import math
import unittest
from PIL import ImageChops
from dreamreader.companion_art import MotionPose, PALETTES, blink_amount, companion_frame, motion_pose, thought_frame


class CompanionMotionTests(unittest.TestCase):
    def test_small_continuous_gestures_across_phrase_and_cycle_boundaries(self):
        previous = motion_pose(0, 1)
        for i in range(1, 1271):
            pose = motion_pose(i/100, 1)
            for name in ('head_x', 'head_y', 'breath', 'left_tap', 'right_tap'):
                self.assertLess(abs(getattr(pose, name)-getattr(previous, name)), .06)
                self.assertLessEqual(abs(getattr(pose, name)), .81)
            self.assertLess(abs(pose.blink-previous.blink), .18)
            previous = pose

    def test_monitor_and_desk_never_swap_with_head_hands_or_eyelids(self):
        still = companion_frame(MotionPose())
        for t in (1.5, 3.18, 3.22, 6.2, 8.5, 10.0):
            active = companion_frame(motion_pose(t, 1))
            for region in ((0, 139, 230, 210), (125, 65, 183, 126)):
                self.assertIsNone(ImageChops.difference(still.crop(region).convert('RGB'), active.crop(region).convert('RGB')).getbbox())
        self.assertIsNotNone(ImageChops.difference(still.convert('RGB'), companion_frame(motion_pose(1,1)).convert('RGB')).getbbox())

    def test_reduced_motion_is_fully_still_including_blink_and_hands(self):
        for t in (0, 3.2, 8.5, 100, 100000):
            self.assertEqual(motion_pose(t, 1, reduced=True), MotionPose())
        self.assertEqual(motion_pose(2, 0).left_tap, 0)
        self.assertEqual(motion_pose(2, 0).right_tap, 0)

    def test_thought_colours_have_text_contrast_and_no_clipped_top(self):
        def luminance(hex_colour):
            values = [int(hex_colour[i:i+2],16)/255 for i in (1,3,5)]
            values = [v/12.92 if v <= .04045 else ((v+.055)/1.055)**2.4 for v in values]
            return sum(a*b for a,b in zip(values,(.2126,.7152,.0722)))
        for state, palette in PALETTES.items():
            values = sorted((luminance(palette['fill']), luminance(palette['ink'])))
            self.assertGreaterEqual((values[1]+.05)/(values[0]+.05), 4.5)
            thought = thought_frame(state)
            self.assertEqual(thought.size, (230,210))
            self.assertIsNone(thought.getchannel('A').crop((0,0,230,1)).getbbox())
            self.assertLessEqual(thought.getchannel('A').getbbox()[3], 49)
        self.assertEqual(thought_frame.cache_info().maxsize, 3)


if __name__ == '__main__':
    unittest.main()
