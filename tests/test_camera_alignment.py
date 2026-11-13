"""Full-range absolute alignment, stable acquisition, projection, and blocking."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
import cv2
import config
from camera.movement import MovementController, camera_to_arena
from camera.pose_tracker import PoseTracker, PoseData, LM_LEFT_WRIST, LM_RIGHT_WRIST
from camera.calibration import CalibrationData
from camera.gesture_detector import GestureDetector
from core.tracking import TrackingData
from gameplay.player import Player
from gameplay.enemy import Enemy
from gameplay.spacing import separate_fighters
from ui.camera_preview import render_preview, preview_key
from test_stable_movement import body
from test_punch_boundary import pose


class AlignmentTests(unittest.TestCase):
    def settle(self, controller, x, mirror=False, count=30, sensitivity=1):
        for _ in range(count):
            controller.update(body(x), 1 / 30, mirror, sensitivity)
        self.assertTrue(controller.valid)
        return controller.position

    def test_five_camera_positions_cover_entire_arena_in_both_mirror_modes(self):
        for mirror in (False, True):
            for x, expected in ((0.1, 0), (0.3, 0.25), (0.5, 0.5), (0.7, 0.75), (0.9, 1)):
                m = MovementController()
                self.settle(m, x, mirror)
                self.assertAlmostEqual(m.position, 1 - expected if mirror else expected)

    def test_points_outside_usable_lane_clamp_to_edges(self):
        for x, expected in ((-0.2, 0), (0.01, 0), (0.99, 1), (1.2, 1)):
            self.assertEqual(camera_to_arena(x), expected)

    def test_stops_and_reversals_never_accumulate_offsets(self):
        m = MovementController()
        for x in (0.5, 0.54, 0.58, 0.7, 0.9, 0.7, 0.58, 0.3, 0.1, 0.3, 0.5):
            self.assertAlmostEqual(self.settle(m, x), camera_to_arena(x))

    def test_response_setting_does_not_change_destination(self):
        for response in (0.5, 1, 2):
            m = MovementController()
            self.assertAlmostEqual(self.settle(m, 0.7, sensitivity=response), 0.75)

    def test_midstream_mirror_change_reacquires_before_new_absolute_target(self):
        m = MovementController()
        self.settle(m, 0.7)
        before = m.position
        m.update(body(0.7), 1 / 30, True)
        self.assertFalse(m.valid)
        self.assertEqual(m.position, before)
        self.assertAlmostEqual(self.settle(m, 0.7, True), 0.25)

    def test_reacquisition_freezes_then_follows_without_teleporting(self):
        m = MovementController()
        self.settle(m, 0.3)
        p = Player(392)
        m.lose()
        for i in range(6):
            before = p.x
            target = m.update(body(0.85), 1 / 30, False)
            p.update(
                1 / 30,
                TrackingData(present=True, movement_valid=m.valid, horizontal_position=target),
                i / 30,
            )
            self.assertLessEqual(abs(p.x - before), p.move_speed / 30 + 1e-6)
            if i < 4:
                self.assertEqual(p.x, 392)
        self.assertAlmostEqual(m.position, 0.9375)
        self.assertGreater(p.x, 392)

    def test_game_tracking_passes_response_without_distorting_target(self):
        from test_camera_tracking import CameraTrackingTests

        fixture = CameraTrackingTests()
        for response in (0.5, 2):
            game = fixture.make_game()
            game.settings["sensitivity"] = response
            fixture.settle(game, fixture.pose(0.3), 1.8)
            self.assertAlmostEqual(game.tracking.horizontal_position, 0.75)
            self.assertEqual(game.tracking.movement_response, response)

    def test_recenter_cannot_leave_a_permanent_offset(self):
        m = MovementController()
        self.settle(m, 0.7)
        for _ in range(3):
            m.recenter(0.2)
            self.assertEqual(m.position, 0.2)
            self.assertAlmostEqual(self.settle(m, 0.7), 0.75)

    def test_actual_player_reaches_legal_endpoints_with_fixed_size(self):
        low = config.ARENA_MARGIN + config.FIGHTER_BODY_WIDTH / 2
        for target in (0, 0.25, 0.5, 0.75, 1):
            p = Player(640)
            for i in range(240):
                p.update(1 / 60, TrackingData(present=True, horizontal_position=target), i / 60)
            self.assertLessEqual(abs(p.x - (low + target * (1280 - 2 * low))), 0.5)
            self.assertEqual(p.scale, 1)

    def test_response_changes_acceleration_but_keeps_maximum_speed_and_endpoint(self):
        speeds = []
        for response in (0.5, 1, 2):
            p = Player(400)
            data = TrackingData(present=True, horizontal_position=1, movement_response=response)
            p.update(1 / 60, data, 0)
            speeds.append(p.x - 400)
            for i in range(360):
                before = p.x
                p.update(1 / 60, data, i / 60)
                self.assertLessEqual(abs(p.x - before), p.move_speed / 60 + 1e-6)
            self.assertLessEqual(abs(p.x - (1280 - config.ARENA_MARGIN - p.body_w / 2)), 0.5)
        self.assertLess(speeds[0], speeds[1])
        self.assertLess(speeds[1], speeds[2])

    def test_opponent_blocks_destination_without_discarding_it(self):
        p = Player(500)
        e = Enemy(config.ENEMIES["jessie"], 760)
        data = TrackingData(present=True, horizontal_position=0.8)
        for i in range(120):
            before = p.x
            p.update(1 / 60, data, i / 60, defer_motion=True)
            separate_fighters(p, e, before, e.x)
            p.finalize_motion(1 / 60, before)
        self.assertAlmostEqual(e.x - p.x, (p.body_w + e.body_w) / 2 + 8)
        self.assertEqual(p.state, "idle")
        self.assertEqual(data.horizontal_position, 0.8)
        e.x = 1136
        for i in range(180):
            before = p.x
            p.update(1 / 60, data, i / 60, defer_motion=True)
            separate_fighters(p, e, before, e.x)
            p.finalize_motion(1 / 60, before)
        self.assertLessEqual(abs(p.x - (144 + 0.8 * 992)), 0.5)
        self.assertGreater(e.x, p.x)


class PreviewProjectionTests(unittest.TestCase):
    def setUp(self):
        self.tracker = PoseTracker()
        self.detector = GestureDetector()
        self.frame = np.zeros((360, 640, 3), np.uint8)
        self.frame[:, :100] = (25, 50, 75)
        self.cal = CalibrationData(torso_height=0.4, arm_length=0.4, punch_direction=1)

    def test_mirrored_image_with_no_pose_flips_once(self):
        result = self.tracker.draw_debug_frame(self.frame, PoseData(False), mirror=True)
        self.assertTrue(np.array_equal(result, cv2.flip(self.frame, 1)))

    def test_landmarks_reflect_without_swapping_ids_or_reversing_labels(self):
        p = pose(left_x=0.2, right_x=0.7)
        before = dict(p.landmarks)
        for mirror in (False, True):
            with patch("camera.pose_tracker.cv2.putText") as text, patch(
                "camera.pose_tracker.cv2.circle"
            ) as circle:
                self.tracker.draw_debug_frame(self.frame, p, mirror=mirror)
                calls = {call.args[1]: call.args[2] for call in text.call_args_list}
                self.assertEqual(set(calls), {"LEFT", "RIGHT"})
                left = [
                    call
                    for call in circle.call_args_list
                    if call.args[3] == config.ARM_LEFT_COLOR[::-1]
                ][0]
                self.assertEqual(left.args[1][0], round((0.8 if mirror else 0.2) * 639))
        self.assertEqual(p.landmarks, before)

    def test_crossed_wrists_keep_readable_separate_anatomical_labels(self):
        p = pose(left_x=0.5, right_x=0.5)
        with patch("camera.pose_tracker.cv2.putText") as text:
            self.tracker.draw_debug_frame(self.frame, p, mirror=True)
        labels = {call.args[1]: call.args[2] for call in text.call_args_list}
        self.assertGreaterEqual(labels["RIGHT"][1] - labels["LEFT"][1], 20)

    def test_boundary_is_projected_using_raw_detection_geometry(self):
        p = pose()
        raw = self.detector.boundary_for(p, self.cal)
        for mirror in (False, True):
            with patch("cv2.line") as line:
                self.detector.draw_punch_boundary(self.frame, p, self.cal, mirror=mirror)
                self.assertEqual(
                    line.call_args.args[1][0], round((1 - raw.x if mirror else raw.x) * 639)
                )
        self.assertEqual(self.detector.boundary_for(p, self.cal), raw)

    def test_shared_renderer_draws_readable_limits_in_both_mirror_modes(self):
        for mirror in (False, True):
            g = SimpleNamespace(
                settings={"mirror_input": mirror},
                raw_landmarks=False,
                pose_tracker=self.tracker,
                gestures=self.detector,
                calibrator=SimpleNamespace(existing=self.cal),
            )
            result = render_preview(g, self.frame, PoseData(False))
            self.assertEqual(result.shape, self.frame.shape)
            for fraction in (0.1, 0.5, 0.9):
                x = round(fraction * 639)
                self.assertGreater(int(result[30, x].max()), 100)

    def test_mirror_toggle_invalidates_cached_previews(self):
        g = SimpleNamespace(
            tracking=TrackingData(sample_id=2),
            settings={"mirror_input": False},
            raw_landmarks=False,
            gestures=self.detector,
            last_pose=PoseData(False),
            last_camera_frame=self.frame,
        )
        old = preview_key(g)
        g.settings["mirror_input"] = True
        self.assertNotEqual(old, preview_key(g))

    def test_mirror_display_cannot_change_anatomical_punch_events(self):
        for mirror in (False, True):
            d = GestureDetector()
            d.update(pose(), 0.05, self.cal, now=1)
            d.update(pose(left_x=0.81), 0.05, self.cal, now=1.05)
            self.assertTrue(d.left_punch)
            self.assertFalse(d.right_punch)
            d.draw_punch_boundary(self.frame, pose(left_x=0.81), self.cal, mirror=mirror)
            self.assertTrue(d.left_punch)
            self.assertFalse(d.right_punch)


class AllCameraViewsTests(unittest.TestCase):
    from test_game_startup import GameStartupTests

    setUp = GameStartupTests.setUp

    def test_all_four_views_refresh_the_projection_when_mirror_changes(self):
        from ui.screens import CameraDebugView, CalibrationScreen
        from ui.settings import SettingsScene

        game = self.game
        game.settings["input_mode"] = "keyboard"
        game.start_new_game()
        fight = game.states.current
        game.settings["input_mode"] = "camera"
        game.last_camera_frame = np.zeros((360, 640, 3), np.uint8)
        game.last_pose = PoseData(False)
        game.tracking = TrackingData(sample_id=5)
        for view in ("gameplay", "settings", "setup", "debug"):
            settings = SettingsScene(game)
            settings.tab = 1
            settings._build_rows()
            setup = CalibrationScreen(game)
            debug = CameraDebugView(game)
            for mirror in (False, True):
                game.settings["mirror_input"] = mirror
                with patch.object(
                    game.pose_tracker, "draw_debug_frame", wraps=game.pose_tracker.draw_debug_frame
                ) as draw, patch.object(
                    game,
                    "poll_camera_for_calibration",
                    return_value=(game.tracking, game.last_pose),
                ):
                    if view == "gameplay":
                        fight._draw_camera_preview(game.canvas)
                    elif view == "settings":
                        settings.draw(game.canvas)
                    elif view == "setup":
                        setup.update(0.016)
                    else:
                        debug.update(0.016)
                    self.assertEqual(draw.call_count, 1, view)
                    self.assertEqual(draw.call_args.kwargs["mirror"], mirror)
                    if view == "gameplay":
                        fight._draw_camera_preview(game.canvas)
                    elif view == "settings":
                        settings.draw(game.canvas)
                    elif view == "setup":
                        setup.update(0.016)
                    else:
                        debug.update(0.016)
                    self.assertEqual(draw.call_count, 1, view)
