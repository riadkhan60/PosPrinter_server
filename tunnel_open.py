import subprocess
import sys
import os


def start_cloudflare_tunnel():
    cloudflared_path = r"C:\Program Files\Cloudflare\bin\cloudflared.exe"
    tunnel_name = "print-server-locale"

    try:
        subprocess.Popen(
            [cloudflared_path, "tunnel", "run", tunnel_name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        print("Cloudflare Tunnel started.")
    except Exception as e:
        print(f"Failed to start Cloudflare Tunnel: {e}")
