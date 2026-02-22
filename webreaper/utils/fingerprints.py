"""Browser fingerprints and stealth utilities."""

import random
from typing import Dict, List, Any


class BrowserFingerprints:
    """Generate realistic browser fingerprints."""
    
    # Realistic user agents
    USER_AGENTS = [
        # Chrome on Windows
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        # Chrome on Mac
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        # Firefox
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/121.0",
        # Safari
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
        # Edge
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    ]
    
    SCREEN_RESOLUTIONS = [
        (1920, 1080), (1366, 768), (1440, 900), (1536, 864),
        (1280, 720), (1600, 900), (1280, 1024), (1680, 1050),
        (1920, 1200), (2560, 1440), (2560, 1080), (3440, 1440),
    ]
    
    COLOR_DEPTHS = [24, 32]
    PIXEL_RATIOS = [1.0, 1.25, 1.5, 2.0]
    
    HARDWARE_CONCURRENCY = [2, 4, 6, 8, 12, 16]
    DEVICE_MEMORY = [2, 4, 8, 16, 32]
    
    WEBGL_RENDERERS = [
        "ANGLE (NVIDIA, NVIDIA GeForce GTX 1050 Ti Direct3D11 vs_5_0 ps_5_0, D3D11)",
        "ANGLE (Intel, Intel(R) UHD Graphics 620 Direct3D11 vs_5_0 ps_5_0, D3D11)",
        "ANGLE (AMD, AMD Radeon(TM) Graphics Direct3D11 vs_5_0 ps_5_0, D3D11)",
        "Apple GPU",
        "Apple M1",
        "Apple M2",
    ]
    
    PLATFORMS = ["Win32", "MacIntel", "Linux x86_64"]
    
    TIMEZONES = [
        "America/New_York", "America/Los_Angeles", "America/Chicago",
        "Europe/London", "Europe/Paris", "Europe/Berlin",
        "Asia/Tokyo", "Asia/Shanghai", "Asia/Singapore",
        "Australia/Sydney", "Pacific/Auckland",
    ]
    
    LANGUAGES = [
        "en-US,en;q=0.9",
        "en-GB,en;q=0.9",
        "en;q=0.9,fr;q=0.8",
        "de-DE,de;q=0.9,en;q=0.8",
        "ja-JP,ja;q=0.9,en;q=0.8",
    ]
    
    @classmethod
    def get_random_fingerprint(cls) -> Dict[str, Any]:
        """Generate a complete random browser fingerprint."""
        screen = random.choice(cls.SCREEN_RESOLUTIONS)
        platform = random.choice(cls.PLATFORMS)
        
        return {
            "user_agent": random.choice(cls.USER_AGENTS),
            "screen": {
                "width": screen[0],
                "height": screen[1],
                "availWidth": screen[0] - random.randint(0, 20),
                "availHeight": screen[1] - random.randint(40, 100),
                "colorDepth": random.choice(cls.COLOR_DEPTHS),
                "pixelDepth": random.choice(cls.COLOR_DEPTHS),
                "pixelRatio": random.choice(cls.PIXEL_RATIOS),
            },
            "navigator": {
                "platform": platform,
                "hardwareConcurrency": random.choice(cls.HARDWARE_CONCURRENCY),
                "deviceMemory": random.choice(cls.DEVICE_MEMORY),
                "maxTouchPoints": 0 if platform == "Win32" else random.choice([0, 5]),
                "language": random.choice(cls.LANGUAGES),
                "languages": random.choice(cls.LANGUAGES).split(","),
                "onLine": True,
                "cookieEnabled": True,
            },
            "webgl": {
                "vendor": "Google Inc. (NVIDIA)" if "ANGLE" in random.choice(cls.WEBGL_RENDERERS) else "Apple Inc.",
                "renderer": random.choice(cls.WEBGL_RENDERERS),
            },
            "timezone": random.choice(cls.TIMEZONES),
            "timezoneOffset": random.randint(-12, 14) * 60,  # Minutes from UTC
        }
    
    @classmethod
    def get_chrome_fingerprint(cls) -> Dict[str, Any]:
        """Generate a Chrome-specific fingerprint."""
        screen = random.choice(cls.SCREEN_RESOLUTIONS)
        
        return {
            "user_agent": f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{random.randint(118, 121)}.0.0.0 Safari/537.36",
            "screen": {
                "width": screen[0],
                "height": screen[1],
                "availWidth": screen[0],
                "availHeight": screen[1] - 40,
                "colorDepth": 24,
                "pixelDepth": 24,
                "pixelRatio": 1.0,
            },
            "navigator": {
                "platform": "Win32",
                "hardwareConcurrency": random.choice([4, 8, 12]),
                "deviceMemory": random.choice([4, 8, 16]),
                "maxTouchPoints": 0,
                "language": "en-US,en;q=0.9",
                "languages": ["en-US", "en"],
                "onLine": True,
                "cookieEnabled": True,
            },
            "webgl": {
                "vendor": "Google Inc. (NVIDIA)",
                "renderer": "ANGLE (NVIDIA, NVIDIA GeForce GTX 1050 Ti Direct3D11 vs_5_0 ps_5_0, D3D11)",
            },
            "timezone": "America/New_York",
            "timezoneOffset": 300,
        }
    
    @classmethod
    def get_firefox_fingerprint(cls) -> Dict[str, Any]:
        """Generate a Firefox-specific fingerprint."""
        screen = random.choice(cls.SCREEN_RESOLUTIONS)
        
        return {
            "user_agent": f"Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/{random.randint(119, 122)}.0",
            "screen": {
                "width": screen[0],
                "height": screen[1],
                "availWidth": screen[0],
                "availHeight": screen[1] - 40,
                "colorDepth": 24,
                "pixelDepth": 24,
                "pixelRatio": 1.0,
            },
            "navigator": {
                "platform": "Win32",
                "hardwareConcurrency": random.choice([4, 8]),
                "deviceMemory": None,  # Firefox doesn't expose this
                "maxTouchPoints": 0,
                "language": "en-US",
                "languages": ["en-US", "en"],
                "onLine": True,
                "cookieEnabled": True,
                "buildID": "20231201",  # Firefox-specific
            },
            "webgl": {
                "vendor": "Mozilla",
                "renderer": "Mozilla",
            },
            "timezone": "America/Los_Angeles",
            "timezoneOffset": 480,
        }
    
    @classmethod
    def get_mobile_fingerprint(cls) -> Dict[str, Any]:
        """Generate a mobile browser fingerprint."""
        mobile_screens = [(375, 667), (414, 896), (390, 844), (360, 740)]
        screen = random.choice(mobile_screens)
        
        return {
            "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1",
            "screen": {
                "width": screen[0],
                "height": screen[1],
                "availWidth": screen[0],
                "availHeight": screen[1] - 100,  # Account for browser chrome
                "colorDepth": 32,
                "pixelDepth": 32,
                "pixelRatio": random.choice([2.0, 3.0]),
            },
            "navigator": {
                "platform": "iPhone",
                "hardwareConcurrency": random.choice([4, 6]),
                "deviceMemory": None,
                "maxTouchPoints": 5,
                "language": "en-US,en;q=0.9",
                "languages": ["en-US", "en"],
                "onLine": True,
                "cookieEnabled": True,
            },
            "webgl": {
                "vendor": "Apple Inc.",
                "renderer": "Apple GPU",
            },
            "timezone": "America/Chicago",
            "timezoneOffset": 360,
        }
