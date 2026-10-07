"""Non-gameplay screens: victory, defeat, camera error, calibration,
level select, load game, and the camera debug view.
"""

from __future__ import annotations

from typing import List, Optional

import pygame

import config
from core.state_manager import Scene
from ui.fonts import render_spaced

C = config.COLORS


class _MenuMixin:
    """Shared keyboard/mouse navigation for simple option lists."""

    def _nav(self, event, count: int) -> bool:
        if event.type == pygame.KEYDOWN:
            key = pygame.key.name(event.key)
            if key in ("up", "w"):
                self.selected = (self.selected - 1) % count
                self.game.audio.play("menu_move")
                return True
            if key in ("down", "s"):
                self.selected = (self.selected + 1) % count
                self.game.audio.play("menu_move")
                return True
            if key in ("return", "space"):
                self._activate()
                return True
        elif event.type == pygame.MOUSEMOTION:
            for i, rect in enumerate(self._rects):
                if rect.collidepoint(event.pos) and i != self.selected:
                    self.selected = i
                    self.game.audio.play("menu_move")
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i, rect in enumerate(self._rects):
                if rect.collidepoint(event.pos):
                    self.selected = i
                    self._activate()
                    return True
        return False

    def _draw_buttons(self, surface, labels: List[str], y0: int,
                      center_x: int) -> None:
        f = self.game.fonts
        self._rects = []
        y = y0
        for i, label in enumerate(labels):
            hover = i == self.selected
            text = f["medium"].render(label, True,
                                      C["title_white"] if hover else C["text"])
            rect = pygame.Rect(center_x - 130, y - 14, 260, 46)
            self._rects.append(rect)
            if hover:
                pygame.draw.rect(surface, (52, 46, 40, 200), rect)
                pygame.draw.rect(surface, C["accent_red"], (rect.x, rect.y, 4, 46))
            surface.blit(text, text.get_rect(center=(center_x, y + 8)))
            y += 56


# ---------------------------------------------------------------------------
class VictoryScreen(Scene, _MenuMixin):
    name = "victory"

    def __init__(self, game, enemy_name: Optional[str] = None,
                 is_final: Optional[bool] = None) -> None:
        super().__init__(game)
        self.selected = 0
        self._rects = []
        self.enemy_name = game.progression.opponent["name"] if enemy_name is None else enemy_name
        self.is_final = game.progression.is_final_fight if is_final is None else is_final

    def enter(self) -> None:
        self.selected = 0
        self.game.audio.play("victory")

    def _activate(self) -> None:
        self.game.audio.play("menu_select")
        if self.selected == 0:      # NEXT FIGHT / MAIN MENU handled below
            if self.is_final:
                self.game.to_main_menu()
            else:
                self.game.next_fight()
        else:
            self.game.to_main_menu()

    def handle_event(self, event: pygame.event.Event) -> None:
        self._nav(event, 2)

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(C["charcoal_dark"])
        f = self.game.fonts
        title = f["big"].render("YOU WIN", True, C["title_white"])
        surface.blit(title, title.get_rect(center=(config.BASE_WIDTH // 2, 210)))
        subtitle = f["medium"].render(
            f"YOU DEFEATED {self.enemy_name.upper()}",
            True, C["text_dim"])
        surface.blit(subtitle, subtitle.get_rect(center=(config.BASE_WIDTH // 2, 290)))
        if self.is_final:
            champion = f["medium"].render("PANAY CHAMPION", True, C["accent_red_bright"])
            surface.blit(champion, champion.get_rect(center=(config.BASE_WIDTH // 2, 330)))
        labels = ["MAIN MENU" if self.is_final else "NEXT FIGHT", "MAIN MENU"]
        self._draw_buttons(surface, labels, 400, config.BASE_WIDTH // 2)


# ---------------------------------------------------------------------------
class DefeatScreen(Scene, _MenuMixin):
    name = "defeat"

    def __init__(self, game) -> None:
        super().__init__(game)
        self.selected = 0
        self._rects = []
        self.enemy_name = ""

    def enter(self) -> None:
        self.selected = 0
        self.enemy_name = self.game.progression.opponent["name"]
        self.game.audio.play("defeat")

    def _activate(self) -> None:
        self.game.audio.play("menu_select")
        if self.selected == 0:
            self.game.retry_fight()
        else:
            self.game.to_main_menu()

    def handle_event(self, event: pygame.event.Event) -> None:
        self._nav(event, 2)

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(C["charcoal_dark"])
        f = self.game.fonts
        title = f["big"].render("YOU LOST", True, C["hp_red"])
        surface.blit(title, title.get_rect(center=(config.BASE_WIDTH // 2, 210)))
        subtitle = f["medium"].render(
            f"{self.enemy_name.upper()} WINS THE ROUND", True, C["text_dim"])
        surface.blit(subtitle, subtitle.get_rect(center=(config.BASE_WIDTH // 2, 290)))
        self._draw_buttons(surface, ["RETRY", "MAIN MENU"], 400,
                           config.BASE_WIDTH // 2)


# ---------------------------------------------------------------------------
class CameraErrorScreen(Scene, _MenuMixin):
    name = "camera_error"

    def __init__(self, game, message: str = "") -> None:
        super().__init__(game)
        self.message = message or "Please connect a webcam and try again."
        self.selected = 0
        self._rects = []

    def enter(self) -> None:
        self.selected = 0

    def _activate(self) -> None:
        self.game.audio.play("menu_select")
        if self.selected == 0:      # RETRY
            if self.game.camera.open(self.game.settings["camera_index"]):
                self.game.start_calibration()
            else:
                self.message = "Still no camera. Connect a webcam and retry."
        elif self.selected == 1:    # KEYBOARD MODE
            self.game.settings["input_mode"] = "keyboard"
            self.game.apply_settings_changes()
            self.game.start_calibration()
        else:                       # MAIN MENU
            self.game.to_main_menu()

    def handle_event(self, event: pygame.event.Event) -> None:
        self._nav(event, 3)

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(C["charcoal_dark"])
        f = self.game.fonts
        title = f["big"].render("CAMERA NOT DETECTED", True, C["hp_red"])
        surface.blit(title, title.get_rect(center=(config.BASE_WIDTH // 2, 190)))
        msg = f["small"].render(self.message, True, C["text"])
        surface.blit(msg, msg.get_rect(center=(config.BASE_WIDTH // 2, 260)))
        note = f["small"].render(
            "POSE TRACKING UNAVAILABLE - KEYBOARD MODE IS AVAILABLE",
            True, C["warn_yellow"])
        surface.blit(note, note.get_rect(center=(config.BASE_WIDTH // 2, 310)))
        self._draw_buttons(surface, ["RETRY", "KEYBOARD MODE", "MAIN MENU"],
                           400, config.BASE_WIDTH // 2)


# ---------------------------------------------------------------------------
class CalibrationScreen(Scene, _MenuMixin):
    """First-run calibration: measure the player's neutral body scale."""

    name = "calibration"

    def __init__(self, game, from_settings: bool = False) -> None:
        super().__init__(game)
        self.from_settings = from_settings
        self.selected = 0
        self._rects = []
        self._phase = "collecting"   # collecting | done
        self._result_text = ""
        self._preview = None

    def enter(self) -> None:
        self.selected = 0
        self.game.calibrator.start()
        self._phase = "collecting"

    def handle_event(self, event: pygame.event.Event) -> None:
        if self._phase == "done":
            self._nav(event, 2)
            return
        if event.type == pygame.KEYDOWN:
            key = pygame.key.name(event.key)
            if key in ("escape",):
                self._skip()
            if key in ("return", "space"):
                self._skip()

    def _skip(self) -> None:
        self.game.audio.play("menu_select")
        if self._phase == "done":
            if self.selected == 0:
                self.game.on_calibration_done(skip=True)
            else:
                self.game.on_calibration_done(skip=True, back=True)
        else:
            self.game.on_calibration_done(skip=True)

    def _activate(self) -> None:
        self._skip()

    def update(self, dt: float) -> None:
        if self._phase != "collecting":
            return
        game = self.game
        tracking, pose = game.poll_camera_for_calibration()
        
        if pose is not None and game.last_camera_frame is not None:
            frame = game.last_camera_frame
            if game.pose_tracker.available:
                frame = game.pose_tracker.draw_debug_frame(frame, pose)
            self._preview = self._to_surface(frame)

        complete = game.calibrator.process(pose, dt)
        if complete:
            data = game.calibrator.finish()
            game.settings["calibration"] = data.to_dict()
            game.apply_settings_changes()
            self._phase = "done"
            self._result_text = (
                f"CALIBRATED - SHOULDER {data.shoulder_width:.2f}  "
                f"TORSO {data.torso_height:.2f}")
            game.audio.play("menu_select")

    def _to_surface(self, bgr_frame):
        rgb = bgr_frame[:, :, ::-1]
        surf = pygame.image.frombuffer(rgb.copy(), (rgb.shape[1], rgb.shape[0]),
                                       "RGB")
        return pygame.transform.scale(surf, (320, 180))

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(C["charcoal_dark"])
        f = self.game.fonts
        title = f["large"].render("CAMERA CALIBRATION", True, C["title_white"])
        surface.blit(title, (60, 50))

        if self._phase == "collecting":
            c = self.game.calibrator
            
            y = 140
            if c.tracking_lost or c.body_not_detected:
                msg = "TRACKING LOST - Return to the center of the frame" if c.tracking_lost else "BODY NOT FULLY DETECTED - Move backward"
                warn = f["medium"].render(msg, True, C["hp_red"])
                surface.blit(warn, (60, y))
            else:
                phase_msgs = {
                    1: ("NEUTRAL STANCE", "Stand naturally with hands down"),
                    2: ("RAISE BOTH ARMS", "Reach for the sky"),
                    3: ("BOXING GUARD", "Hands up protecting your face"),
                    4: ("SIDE-ON FIGHTING STANCE", "Turn sideways like a boxer"),
                }
                step, desc = phase_msgs.get(c.phase, ("WAIT", ""))
                
                step_text = f["large"].render(step, True, C["warn_yellow"])
                surface.blit(step_text, (60, y))
                y += 40
                desc_text = f["medium"].render(desc, True, C["text"])
                surface.blit(desc_text, (60, y))
                
                y += 80
                
                if c.hold_time > 0.05:
                    status = "Detected! Hold..."
                    color = C["ok_green"]
                else:
                    status = "Waiting for pose..."
                    color = C["text_dim"]
                    
                status_text = f["medium"].render(status, True, color)
                surface.blit(status_text, (60, y))
                
                # Progress bar
                y += 40
                progress = min(1.0, c.hold_time / 1.0) # HOLD_TIME_REQ = 1.0
                pygame.draw.rect(surface, C["hp_empty"], (60, y, 400, 24))
                if progress > 0:
                    pygame.draw.rect(surface, C["ok_green"], (60, y, int(400 * progress), 24))
                pygame.draw.rect(surface, C["border"], (60, y, 400, 24), 2)
            
            skip = f["small"].render("PRESS ESC TO SKIP", True, C["text_dim"])
            surface.blit(skip, (60, 420))
            
            # camera preview corner
            if self._preview is not None:
                surface.blit(self._preview, (config.BASE_WIDTH - 360, 140))
                pygame.draw.rect(surface, C["border"],
                                 (config.BASE_WIDTH - 360, 140, 320, 180), 1)
        else:
            done = f["big"].render("CALIBRATION COMPLETE", True, C["ok_green"])
            surface.blit(done, done.get_rect(center=(config.BASE_WIDTH // 2, 240)))
            result = f["small"].render(self._result_text, True, C["text"])
            surface.blit(result, result.get_rect(center=(config.BASE_WIDTH // 2, 310)))
            self._draw_buttons(surface, ["CONTINUE", "MAIN MENU"], 400,
                               config.BASE_WIDTH // 2)


# ---------------------------------------------------------------------------
class LoadGameScreen(Scene, _MenuMixin):
    name = "load_game"

    def __init__(self, game) -> None:
        super().__init__(game)
        self.selected = 0
        self._rects = []
        self._slots: List[dict] = []

    def enter(self) -> None:
        self.selected = 0
        self._slots = []
        for slot in range(1, config.NUM_SAVE_SLOTS + 1):
            summary = self.game.save_manager.slot_summary(slot)
            self._slots.append(summary or {"slot": slot, "exists": False})

    def handle_event(self, event: pygame.event.Event) -> None:
        if self._nav(event, len(self._slots) + 1):
            return

    def _activate(self) -> None:
        self.game.audio.play("menu_select")
        if self.selected == len(self._slots):
            self.game.states.pop()      # BACK
            return
        slot = self._slots[self.selected]
        if slot["exists"]:
            self.game.load_save(slot["slot"])
        else:
            self.game.start_new_game(slot_number=slot["slot"])

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(C["charcoal_dark"])
        f = self.game.fonts
        title = f["large"].render("LOAD GAME", True, C["title_white"])
        surface.blit(title, (60, 50))
        hint = f["tiny"].render("EMPTY SLOTS START A NEW GAME", True, C["text_faint"])
        surface.blit(hint, (60, 92))

        self._rects = []
        y = 150
        for i, slot in enumerate(self._slots):
            rect = pygame.Rect(60, y, 700, 64)
            self._rects.append(rect)
            hover = i == self.selected
            if hover:
                pygame.draw.rect(surface, (52, 46, 40), rect)
                pygame.draw.rect(surface, C["accent_red"], (rect.x, rect.y, 4, 64))
            pygame.draw.rect(surface, C["border"], rect, 1)
            head = f["medium"].render(
                f"SLOT {slot['slot']}", True,
                C["title_white"] if hover else C["text"])
            surface.blit(head, (rect.x + 18, rect.y + 8))
            if slot["exists"]:
                sub = f["small"].render(
                    f"{slot['timestamp']}   -   {slot['opponent']} @ {slot['location']}"
                    f"   -   {len(slot['defeated'])} WINS",
                    True, C["text_dim"])
            else:
                sub = f["small"].render("EMPTY", True, C["text_faint"])
            surface.blit(sub, (rect.x + 18, rect.y + 36))
            y += 76

        back_rect = pygame.Rect(60, y + 6, 700, 44)
        self._rects.append(back_rect)
        hover = self.selected == len(self._slots)
        if hover:
            pygame.draw.rect(surface, (52, 46, 40), back_rect)
            pygame.draw.rect(surface, C["accent_red"], (back_rect.x, back_rect.y, 4, 44))
        back = f["medium"].render("BACK", True,
                                  C["title_white"] if hover else C["text"])
        surface.blit(back, (back_rect.x + 18, back_rect.y + 10))


# ---------------------------------------------------------------------------
class LevelSelectScreen(Scene, _MenuMixin):
    name = "level_select"

    def __init__(self, game) -> None:
        super().__init__(game)
        self.selected = 0
        self._rects = []

    def enter(self) -> None:
        self.selected = 0

    def handle_event(self, event: pygame.event.Event) -> None:
        self._nav(event, len(self.game.progression.unlocked_opponents()) + 1)

    def _activate(self) -> None:
        self.game.audio.play("menu_select")
        unlocked = self.game.progression.unlocked_opponents()
        if self.selected == len(unlocked):
            self.game.states.pop()
            return
        self.game.fight_opponent(unlocked[self.selected])

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(C["charcoal_dark"])
        f = self.game.fonts
        title = f["large"].render("LEVEL SELECT", True, C["title_white"])
        surface.blit(title, (60, 50))

        self._rects = []
        y = 140
        unlocked = self.game.progression.unlocked_opponents()
        for i, index in enumerate(unlocked):
            enemy = config.ENEMIES[config.OPPONENT_ORDER[index]]
            location = config.LOCATIONS[config.LOCATION_ORDER[index]]
            rect = pygame.Rect(60, y, 700, 58)
            self._rects.append(rect)
            hover = i == self.selected
            if hover:
                pygame.draw.rect(surface, (52, 46, 40), rect)
                pygame.draw.rect(surface, C["accent_red"], (rect.x, rect.y, 4, 58))
            pygame.draw.rect(surface, C["border"], rect, 1)
            name = f["medium"].render(f"{enemy['name'].upper()}", True,
                                      C["title_white"] if hover else C["text"])
            surface.blit(name, (rect.x + 18, rect.y + 8))
            sub = f["small"].render(
                f"{enemy.get('title','').upper()}  -  {location['name'].upper()}",
                True, C["text_dim"])
            surface.blit(sub, (rect.x + 18, rect.y + 34))
            y += 68

        back_rect = pygame.Rect(60, y + 6, 700, 44)
        self._rects.append(back_rect)
        if self.selected == len(unlocked):
            pygame.draw.rect(surface, (52, 46, 40), back_rect)
            pygame.draw.rect(surface, C["accent_red"], (back_rect.x, back_rect.y, 4, 44))
        back = f["medium"].render("BACK", True, C["title_white"] if self.selected == len(unlocked) else C["text"])
        surface.blit(back, (back_rect.x + 18, back_rect.y + 10))


# ---------------------------------------------------------------------------
class CameraDebugView(Scene):
    """Full-screen camera feed with landmarks, metrics and status text."""

    name = "camera_debug"

    def __init__(self, game, back_to: str = "settings") -> None:
        super().__init__(game)
        self.back_to = back_to
        self.fonts = game.fonts
        self._preview = None

    def enter(self) -> None:
        if not self.game.camera_is_open():
            self.game.camera.open(self.game.settings["camera_index"])

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if pygame.key.name(event.key) == "escape":
                self.game.audio.play("menu_move")
                self.game.states.pop()
                self.game.save_manager.save_settings()

    def update(self, dt: float) -> None:
        game = self.game
        tracking, pose = game.poll_camera_for_calibration()
        if game.last_camera_frame is not None:
            frame = game.last_camera_frame
            if game.pose_tracker.available:
                frame = game.pose_tracker.draw_debug_frame(frame, pose)
            rgb = frame[:, :, ::-1]
            surf = pygame.image.frombuffer(rgb.copy(), (rgb.shape[1], rgb.shape[0]), "RGB")
            self._preview = pygame.transform.scale(surf, (800, 450))

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(C["charcoal_dark"])
        f = self.game.fonts
        game = self.game

        if self._preview is not None:
            surface.blit(self._preview, (40, 40))
            pygame.draw.rect(surface, C["border"], (40, 40, 800, 450), 1)

        x = 880
        y = 50
        tracking, pose = game.last_tracking, game.last_pose
        camera_ok = game.camera_is_open()
        rows = [
            ("Camera:", "CONNECTED" if camera_ok else "DISCONNECTED",
             C["ok_green"] if camera_ok else C["hp_red"]),
            ("Pose:", "DETECTED" if (pose and pose.present) else "NONE",
             C["ok_green"] if (pose and pose.present) else C["warn_yellow"]),
            ("Body conf:", f"{tracking.body_confidence:.2f}" if tracking else "0.00",
             C["debug"]),
            ("Player X:", f"{tracking.horizontal_position:.2f}" if tracking else "-",
             C["debug"]),
            ("Distance:", tracking.distance_level if tracking else "-",
             C["warn_yellow"]),
            ("Left Hand:", "DETECTED" if pose and pose.lm(15) and pose.lm(15)[3] > 0.4 else "LOST",
             C["debug"]),
            ("Right Hand:", "DETECTED" if pose and pose.lm(16) and pose.lm(16)[3] > 0.4 else "LOST",
             C["debug"]),
            ("Left Punch:", str(tracking.left_punch) if tracking else "-",
             C["debug"]),
            ("Right Punch:", str(tracking.right_punch) if tracking else "-",
             C["debug"]),
            ("Guard:", str(tracking.guard) if tracking else "-", C["debug"]),
            ("FPS:", f"{game.fps:.0f}", C["debug"]),
        ]
        for label, value, color in rows:
            label_surf = f["small"].render(label, True, C["text_dim"])
            value_surf = f["small"].render(value, True, color)
            surface.blit(label_surf, (x, y))
            surface.blit(value_surf, (x + 160, y))
            y += 32

        hint = f["tiny"].render("ESC TO RETURN", True, C["text_faint"])
        surface.blit(hint, (x, y + 20))
