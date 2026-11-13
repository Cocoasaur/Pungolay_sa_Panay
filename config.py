"""PUNGOLAY SA PANAY - central configuration.

All tunable values live here so balancing the game never requires digging
through gameplay code. Values are grouped by subsystem.
"""

import os

# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------
GAME_TITLE = "PUNGOLAY SA PANAY"
GAME_SUBTITLE_TOP = "PUNGOLAY SA"
GAME_SUBTITLE_BOTTOM = "PANAY"
VERSION = "0.6.7"

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
SPRITES_DIR = os.path.join(ASSETS_DIR, "sprites")
LEVELS_DIR = os.path.join(ASSETS_DIR, "levels")
HUD_DIR = os.path.join(ASSETS_DIR, "hud")
HUD_IMAGE_PATH = os.path.join(HUD_DIR, "hud.png")
MENU_DIR = os.path.join(ASSETS_DIR, "menu")
MENU_IMAGE_PATH = os.path.join(MENU_DIR, "menu.png")
MENU_BACKGROUND_PATH = os.path.join(MENU_DIR, "menu_background_clean.png")
PAUSE_MENU_DIR = os.path.join(ASSETS_DIR, "pause_menu")
PAUSE_MENU_IMAGE_PATH = os.path.join(PAUSE_MENU_DIR, "pause_menu.png")
SCREENS_DIR = os.path.join(ASSETS_DIR, "screens")
FONTS_DIR = os.path.join(ASSETS_DIR, "fonts")
SOUNDS_DIR = os.path.join(ASSETS_DIR, "sounds")
MODELS_DIR = os.path.join(ASSETS_DIR, "models")
SAVES_DIR = os.path.join(BASE_DIR, "saves")
POSE_MODEL_PATH = os.path.join(MODELS_DIR, "pose_landmarker_lite.task")
POSE_CV2_MODEL_PATH = os.path.join(MODELS_DIR, "yolo11n-pose.onnx")
SETTINGS_PATH = os.path.join(SAVES_DIR, "settings.json")

# ---------------------------------------------------------------------------
# Window
# ---------------------------------------------------------------------------
BASE_WIDTH = 1280
BASE_HEIGHT = 720
FPS_TARGET = 60
FULLSCREEN_DEFAULT = False

# Arena geometry (all in base-resolution pixels)
ARENA_MARGIN = 90            # fighters cannot cross this line toward a wall
GROUND_Y = 620               # shared foreground position of the fighters' feet
RING_FLOOR_Y = 520           # top of the ring floor boards
RING_POST_X = 26             # x of the corner posts (both sides)
ROPE_YS = (352, 388, 424)    # y positions of the three ropes

# Shared by the renderer, defensive hitboxes, punch reach, and AI spacing.
FIGHTER_SIZE = 2.0
FIGHTER_BODY_WIDTH = 54 * FIGHTER_SIZE
FIGHTER_BODY_HEIGHT = 120 * FIGHTER_SIZE

# ---------------------------------------------------------------------------
# Color palette (charcoal / warm wood / white / red accent)
# ---------------------------------------------------------------------------
COLORS = {
    "charcoal_dark": (16, 15, 14),
    "charcoal": (24, 22, 20),
    "charcoal_light": (38, 35, 32),
    "panel": (13, 12, 11, 220),
    "border": (58, 51, 44),
    "wood_dark": (36, 26, 18),
    "wood": (58, 42, 28),
    "wood_light": (88, 62, 40),
    "warm_glow": (255, 180, 94),
    "title_white": (242, 240, 234),
    "title_gray": (185, 179, 171),
    "text": (207, 201, 192),
    "text_dim": (138, 130, 120),
    "text_faint": (90, 84, 76),
    "accent_red": (179, 64, 42),
    "accent_red_bright": (222, 84, 56),
    "fighter_white": (240, 240, 236),
    "fighter_outline": (26, 24, 22),
    "glove_red": (196, 46, 34),
    "glove_red_dark": (140, 32, 26),
    "trunks_player": (28, 38, 54),
    "trunks_enemy": (48, 22, 26),
    "hp_red": (188, 54, 42),
    "hp_red_dark": (96, 28, 24),
    "hp_empty": (56, 34, 30),
    "stamina_amber": (214, 168, 74),
    "stamina_empty": (56, 48, 34),
    "ok_green": (110, 180, 110),
    "warn_yellow": (214, 180, 90),
    "debug": (120, 255, 150),
}

# ---------------------------------------------------------------------------
# Player combat stats
# ---------------------------------------------------------------------------
PLAYER = {
    "max_hp": 100,
    "max_stamina": 100,
    "punch_damage": 8,
    "punch_cooldown": 0.35,        # seconds between punches (per hand)
    "punch_cost": 6,               # stamina cost per punch
    "guard_stamina_drain": 9,      # stamina per second while guarding
    "stamina_regen": 14,           # stamina per second when not guarding
    "guard_damage_reduction": 0.70,  # fraction of damage removed while guarding
    "block_stamina_cost": 4,       # stamina cost when a guarded hit connects
    "hit_invuln": 0.35,            # seconds of invulnerability after being hit
    "knockdown_recover_hp": 0.35,  # fraction of max HP restored on get-up
    "move_speed": 340,             # px/sec when tracking a moving target
    "reach": 62,                   # base punch reach in px at scale 1.0
    "punch_active_start": 0.06,    # seconds after punch start when hitbox lives
    "punch_active_end": 0.22,
    "punch_recover": 0.30,
}

# ---------------------------------------------------------------------------
# Enemy archetypes - data driven. Opponent order == progression order.
# style only flavours the telegraph; behaviour comes from the numbers.
# ---------------------------------------------------------------------------
ENEMIES = {
    "jessie": {
        "name": "Jessie",
        "title": "The Tutorial",
        "hp": 100, "damage": 7, "speed": 1.9, "reach": 58,
        "preferred_distance": 120, "aggression": 0.45,
        "guard_chance": 0.10, "retreat_chance": 0.15,
        "attack_delay": 0.35, "recover_time": 0.45, "reaction_time": 0.7,
        "stagger_resist": 0.0, "style": "right_hook", "trunks": (28, 38, 54),
    },
    "jevidiah": {
        "name": "Jevidiah",
        "title": "The Dirty Fighter",
        "hp": 115, "damage": 8, "speed": 2.3, "reach": 56,
        "preferred_distance": 90, "aggression": 0.85,
        "guard_chance": 0.18, "retreat_chance": 0.08,
        "attack_delay": 0.22, "recover_time": 0.38, "reaction_time": 0.5,
        "stagger_resist": 0.05, "style": "swarm", "trunks": (52, 44, 24),
    },
    "johnwilt": {
        "name": "Johnwilt",
        "title": "The Distance Fighter",
        "hp": 105, "damage": 9, "speed": 2.2, "reach": 66,
        "preferred_distance": 165, "aggression": 0.55,
        "guard_chance": 0.25, "retreat_chance": 0.45,
        "attack_delay": 0.30, "recover_time": 0.42, "reaction_time": 0.6,
        "stagger_resist": 0.0, "style": "hit_and_run", "trunks": (30, 46, 40),
    },
    "jereme": {
        "name": "Jereme",
        "title": "The Dancer",
        "hp": 100, "damage": 6, "speed": 3.1, "reach": 52,
        "preferred_distance": 130, "aggression": 0.75,
        "guard_chance": 0.12, "retreat_chance": 0.25,
        "attack_delay": 0.18, "recover_time": 0.32, "reaction_time": 0.35,
        "stagger_resist": 0.0, "style": "flurry", "trunks": (44, 40, 52),
    },
    "daniel": {
        "name": "Daniel",
        "title": "The Heavyweight",
        "hp": 170, "damage": 12, "speed": 1.5, "reach": 64,
        "preferred_distance": 105, "aggression": 0.60,
        "guard_chance": 0.22, "retreat_chance": 0.05,
        "attack_delay": 0.42, "recover_time": 0.55, "reaction_time": 0.8,
        "stagger_resist": 0.45, "style": "haymaker", "trunks": (38, 34, 44),
    },
    "blacc_twenti_too": {
        "name": "Blacc Twenti Too",
        "title": "The Power",
        "hp": 150, "damage": 13, "speed": 1.7, "reach": 72,
        "preferred_distance": 140, "aggression": 0.65,
        "guard_chance": 0.20, "retreat_chance": 0.10,
        "attack_delay": 0.45, "recover_time": 0.5, "reaction_time": 0.75,
        "stagger_resist": 0.35, "style": "looping", "trunks": (24, 24, 30),
    },
    "caloy": {
        "name": "Caloy",
        "title": "The Final Boss",
        "hp": 220, "damage": 14, "speed": 1.9, "reach": 70,
        "preferred_distance": 115, "aggression": 0.70,
        "guard_chance": 0.28, "retreat_chance": 0.05,
        "attack_delay": 0.4, "recover_time": 0.48, "reaction_time": 0.55,
        "stagger_resist": 0.55, "style": "boss", "trunks": (58, 30, 20),
    },
}

OPPONENT_ORDER = ["jessie", "jevidiah", "johnwilt", "jereme",
                  "daniel", "blacc_twenti_too", "caloy"]

# ---------------------------------------------------------------------------
# Locations (progression order matches OPPONENT_ORDER)
# ---------------------------------------------------------------------------
LOCATIONS = {
    "black22": {
        "name": "Black 22", "subtitle": "Underground Gym",
        "wall": (46, 34, 26), "wall_top": (30, 22, 17), "floor": (66, 46, 30),
        "accent": (179, 64, 42), "props": ["gym"],
    },
    "citi_hardware": {
        "name": "Citi Hardware", "subtitle": "Iloilo City",
        "wall": (40, 44, 50), "wall_top": (26, 29, 33), "floor": (70, 66, 58),
        "accent": (200, 160, 70), "props": ["shelves"],
    },
    "jaro_plaza": {
        "name": "Jaro Plaza", "subtitle": "Jaro, Iloilo City",
        "wall": (52, 46, 60), "wall_top": (34, 30, 40), "floor": (84, 74, 62),
        "accent": (170, 150, 190), "props": ["plaza"],
    },
    "pavia_plaza": {
        "name": "Pavia Plaza", "subtitle": "Pavia, Iloilo",
        "wall": (54, 58, 50), "wall_top": (36, 39, 33), "floor": (88, 82, 68),
        "accent": (150, 180, 130), "props": ["plaza_palma"],
    },
    "jollibee_sta_barbara": {
        "name": "Jollibee Sta. Barbara", "subtitle": "Sta. Barbara, Iloilo",
        "wall": (66, 40, 34), "wall_top": (44, 27, 23), "floor": (92, 74, 58),
        "accent": (222, 60, 46), "props": ["fastfood"],
    },
    "iloilo_airport": {
        "name": "Iloilo National Airport", "subtitle": "Cabatuan, Iloilo",
        "wall": (48, 60, 74), "wall_top": (32, 40, 50), "floor": (96, 96, 96),
        "accent": (130, 190, 220), "props": ["airport"],
    },
    "caloy_house": {
        "name": "Caloy's House", "subtitle": "The Final Location",
        "wall": (44, 32, 30), "wall_top": (28, 21, 20), "floor": (78, 58, 42),
        "accent": (214, 168, 74), "props": ["living_room"],
    },
}
LOCATION_ORDER = ["black22", "citi_hardware", "jaro_plaza", "pavia_plaza",
                  "jollibee_sta_barbara", "iloilo_airport", "caloy_house"]

# ---------------------------------------------------------------------------
# Camera / vision pipeline
# ---------------------------------------------------------------------------
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 360        # capture is downscaled to this for pose processing
POSE_FRAME_EVERY = 1       # process pose on every captured frame
POSE_CREATE_TIMEOUT = 8.0  # seconds to wait for the pose backend to initialize
POSE_SELFTEST_TIMEOUT = 30.0  # seconds to wait for the mediapipe subprocess test
POSE_BACKEND = "auto"     # "auto" | "mediapipe" | "cv2"
POSE_MIN_BODY_CONFIDENCE = 0.5
POSE_MIN_LANDMARK_VIS = 0.4
TRACKING_LOST_GRACE = 0.4  # seconds of missing pose before movement freezes
TRACKING_LOST_WARNING = 2.5  # seconds missing before a hint is shown

# Movement mapping / smoothing
# Hips are the most stable landmark while a boxer punches or guards.  Keep
# these weights here (rather than in pose_tracker.py) so they remain tunable.
BODY_CENTER_WEIGHTS = {"shoulders": 0.15, "hips": 0.70, "nose": 0.15}
TRACKING_RESPONSE_TIME = 0.085  # seconds; 95% of a move settles in about 250 ms
TRACKING_RESPONSE_TIME_MAX = 0.110  # maximum smoothing-slider response time
TRACKING_LATERAL_DEADBAND = 0.012  # normalized camera-space jitter to ignore
TRACKING_DEPTH_DEADBAND = 0.025    # ratio jitter to ignore around the stance
TRACKING_PUNCH_RECOVERY = 0.30    # hold depth while arm/shoulder tracking settles

TRACKING_SMOOTHING_FACTOR = 0.3    # Exponential moving average factor (0.0 to 1.0)
TRACKING_CONFIDENCE_THRESHOLD = 0.6
MAX_LANDMARK_JUMP = 0.15           # Maximum allowed landmark delta per frame (normalized)

# Deprecated relative/depth mapping constants, retained for compatibility.
# lateral and depth deltas are measured from the resting pose at fight start:
#   hp = DEPTH_NEUTRAL_HP + lateral_delta + depth_delta * DEPTH_MOVE_GAIN
DEPTH_MOVE_GAIN = 1.0        # how strongly depth shifts the boxer
DEPTH_NEUTRAL_HP = 0.35      # boxer's arena position at calibration distance
DEPTH_HP_MIN = 0.05          # far / far-left clamp
DEPTH_HP_MAX = 0.65          # close / near-right clamp (short of the enemy)

# Distance estimation (relative, never claims real centimeters)
DISTANCE_REF_FALLBACK = 0.45     # normalized shoulder width used if uncalibrated
DISTANCE_REF_TORSO_FALLBACK = 0.36
DISTANCE_CLOSE_RATIO = 1.20      # ratio >= this -> CLOSE
DISTANCE_FAR_RATIO = 0.80        # ratio <= this -> FAR
DISTANCE_SMOOTHING = 0.10
DISTANCE_SCALE_MIN = 0.85        # fighter sprite scale at FAR
DISTANCE_SCALE_MAX = 1.20        # fighter sprite scale at CLOSE

# Gesture detection (normalized image units, 640-wide frame)
PUNCH_Z_VELOCITY = 1.1           # wrist z speed needed to count as a punch
PUNCH_Z_FORWARD = 0.06           # wrist must be this far in front of shoulder
PUNCH_ARM_EXTENDED = 0.30        # elbow-wrist distance must exceed this
PUNCH_COOLDOWN = 0.35            # seconds between punches per hand
PUNCH_VELOCITY_THRESHOLD = 0.8   # minimum velocity magnitude for punch detection
PUNCH_CONFIRMATION_TIME = 0.05   # seconds a punch condition must be met to trigger
PUNCH_LINE_REACH = 0.75          # fraction of calibrated arm length ahead of torso
ENEMY_ATTACK_ACTIVE_TIME = 0.16
ARM_FILTER_FAST = 0.012
ARM_FILTER_SLOW = 0.045
POSE_SAMPLE_MAX_AGE = 0.250
ARM_LEFT_COLOR = (0, 210, 255)       # RGB cyan
ARM_RIGHT_COLOR = (255, 140, 0)      # RGB orange
PUNCH_LINE_REARM = 0.15          # hand must retract this far behind the punch line

BLOCK_ENTER_THRESHOLD = 0.35     # max wrist-to-shoulder normalized distance to enter block
BLOCK_EXIT_THRESHOLD = 0.45      # max wrist-to-shoulder normalized distance to exit block
GUARD_HOLD_TIME = 0.15           # seconds wrists must stay up to enter guard

CHARGE_ENTER_THRESHOLD = -0.10   # minimum wrist z-offset (behind torso/shoulder) to enter charge
CHARGE_EXIT_THRESHOLD = -0.05    # maximum wrist z-offset to exit charge
CHARGE_MIN_BEND = 0.4            # max wrist-to-shoulder distance to ensure arm is tucked
HAYMAKER_CHARGE_TIME = 5.0
HAYMAKER_DAMAGE_MULTIPLIER = 2.0

GETUP_HANDS_UP_TIME = 0.5        # seconds both hands must be raised to get up

# OpenCV (YOLO-pose) backend thresholds
POSE_CV2_PERSON_SCORE = 0.35     # min person detection score
POSE_CV2_KEYPOINT_CONF = 0.25    # min keypoint confidence

# ---------------------------------------------------------------------------
# Combat feel
# ---------------------------------------------------------------------------
CRITICAL_HIT_CHANCE = 0.20
CRITICAL_DAMAGE_MULTIPLIER = 2.0
HITSTOP_TIME = 0.07        # seconds both fighters freeze on a landed hit
SCREEN_SHAKE_HIT = 5       # shake magnitude on hit (px)
SCREEN_SHAKE_BIG = 9       # shake magnitude on knockdown
KNOCKDOWN_COUNT_INTERVAL = 0.8  # seconds between count numbers
KNOCKDOWN_MAX_COUNT = 10

# ---------------------------------------------------------------------------
# UI / menus
# ---------------------------------------------------------------------------
FONT_NAMES = ["Liberation Sans", "DejaVu Sans", "Noto Sans", "Arial"]
MENU_ITEMS = ["NEW GAME", "LOAD GAME", "SETTINGS", "QUIT"]

# ---------------------------------------------------------------------------
# Keyboard fallback controls
# ---------------------------------------------------------------------------
KEYS = {
    "left": ("a", "left"),
    "right": ("d", "right"),
    "left_punch": "j",
    "right_punch": "k",
    "guard": "space",
    "get_up": "space",
    "pause": "escape",
    "debug": "f3",
    "fullscreen": "f11",
}

# ---------------------------------------------------------------------------
# Save system
# ---------------------------------------------------------------------------
NUM_SAVE_SLOTS = 3
SAVE_FILENAMES = [f"slot{i}.json" for i in range(1, NUM_SAVE_SLOTS + 1)]

DEFAULT_SETTINGS = {
    "music_volume": 0.35,
    "sfx_volume": 0.7,
    "camera_index": 0,
    "input_mode": "camera",          # "camera" | "keyboard"
    "sensitivity": 1.0,              # camera follower response; never changes viewport mapping
    "smoothing": 0.55,               # deprecated; retained for saved-setting compatibility
    "punch_sensitivity": 1.0,        # confidence (2D) / depth thresholds (3D)
    "punch_line_reach": 0.75,        # calibrated arm fraction; independent of sensitivity
    "distance_sensitivity": 1.0,
    "fullscreen": FULLSCREEN_DEFAULT,
    "debug_mode": False,
    "camera_preview": True,
    "mirror_input": True,            # mirror horizontal camera movement
                                     # (player faces the camera)
    "calibration": None,             # dict from camera/calibration.py
    "last_slot": 1,
    "pose_backend": "auto",          # "auto" | "mediapipe" | "cv2"
}

# Body intent is independent from fast arm filtering.
MOVEMENT_MIN_CONFIDENCE = 0.65
MOVEMENT_ENTER_DISTANCE = 0.018
MOVEMENT_ENTER_TIME = 0.080
MOVEMENT_STOP_VELOCITY = 0.015
MOVEMENT_STOP_TIME = 0.150
MOVEMENT_REACQUIRE_TIME = 0.150
MOVEMENT_MAX_SAMPLE_JUMP = 0.12
MOVEMENT_ACCEL_TIME = 0.150
WALK_ENTER_SPEED = 18.0
WALK_EXIT_SPEED = 7.0
WALK_STOP_TIME = 0.150
FIGHTER_SEPARATION = 8.0
KNOCKDOWN_FALL_TIME = 0.50
GETUP_TIME = 0.52
CHARGE_ENTRY_TIME = 0.10
CHARGE_RELEASE_GRACE = 0.15
CHARGE_LOST_GRACE = 0.30
ANIMATION_CACHE_BYTES = 128 * 1024 * 1024

COLORS.update(
    {
        "charcoal_dark": (23, 21, 18),
        "panel": (31, 28, 24),
        "title_white": (242, 231, 211),
        "text": (226, 215, 196),
        "text_dim": (177, 164, 143),
        "text_faint": (139, 126, 107),
        "border": (100, 85, 66),
        "accent_red": (184, 58, 43),
        "accent_red_bright": (210, 77, 56),
        "warm_glow": (233, 182, 111),
    }
)

# Camera hip-center lane: full arena travel before either hip leaves the frame.
CAMERA_MOVEMENT_LEFT = 0.10
CAMERA_MOVEMENT_RIGHT = 0.90
