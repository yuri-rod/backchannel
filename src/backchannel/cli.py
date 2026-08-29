import argparse
import json
import sys
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import urlopen

from . import config as configuration
from . import mirror, server
from .models import TranscriptError

NGROK_API = "http://127.0.0.1:4040/api/tunnels"


def main(argv=None):
    parser = argparse.ArgumentParser(prog="backchannel")
    parser.add_argument("--config", help="path to config.toml")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("serve", help="run the HTTP server")
    mirror_command = commands.add_parser("mirror", help="mirror the agent transcript")
    mirror_command.add_argument("--once", action="store_true")
    commands.add_parser("token", help="print the share token, creating it if needed")
    url_command = commands.add_parser("url", help="print the public chat URL")
    url_command.add_argument("--api", default=NGROK_API, help="ngrok local API")

    options = parser.parse_args(argv)
    try:
        settings = configuration.load(options.config)
    except configuration.ConfigError as error:
        sys.stderr.write(f"config: {error}\n")
        return 2

    if options.command == "serve":
        sys.stderr.write(f"backchannel on {settings.host}:{settings.port}\n")
        sys.stderr.flush()
        return server.run(settings)
    if options.command == "mirror":
        try:
            return mirror.run(settings, once=options.once)
        except TranscriptError as error:
            sys.stderr.write(f"mirror: {error}\n")
            return 1
    if options.command == "token":
        print(server.load_token(settings.token_file))
        return 0
    return show_url(settings, options.api)


def show_url(settings, api):
    # --api is a URL from the command line, so pin the scheme before opening it.
    # Without this, file:// would turn a typo into a local file read.
    if urlsplit(api).scheme not in ("http", "https"):
        sys.stderr.write(f"--api must be an http(s) URL, got {api!r}\n")
        return 2
    try:
        with urlopen(api, timeout=8) as response:  # noqa: S310 - scheme checked above
            tunnels = json.load(response)["tunnels"]
    except (URLError, OSError, ValueError, KeyError):
        sys.stderr.write("ngrok is not answering on its local API\n")
        return 1
    suffix = f":{settings.port}"
    public = [
        tunnel["public_url"]
        for tunnel in tunnels
        if str(tunnel.get("config", {}).get("addr", "")).endswith(suffix)
    ]
    if not public:
        sys.stderr.write(f"no ngrok tunnel forwards to {suffix}\n")
        return 1
    token = server.load_token(settings.token_file)
    print(f"{public[0]}/?k={token}")
    return 0
