# Service templates

Two long-running processes: `serve` (the HTTP server) and `mirror` (the
transcript tail). Run one instance of each.

## macOS (launchd)

    for command in serve mirror; do
      sed -e "s|PREFIX|$PWD|g" -e "s|COMMAND|$command|g" \
        templates/backchannel.plist.template \
        > ~/Library/LaunchAgents/com.example.backchannel-$command.plist
      launchctl load ~/Library/LaunchAgents/com.example.backchannel-$command.plist
    done

## Linux (systemd user units)

    cp templates/backchannel@.service ~/.config/systemd/user/
    systemctl --user enable --now backchannel@serve backchannel@mirror

The unit assumes the checkout lives at `~/backchannel`; edit `ExecStart` if it
does not.

## About the restart policy

Both templates restart on failure only, and both throttle. That is deliberate.

A supervisor told to restart unconditionally turns one bad config into a hot
loop: the process exits in milliseconds, gets restarted, exits again. On launchd
that is a bare `<key>KeepAlive</key><true/>`; on systemd it is `Restart=always`
with no `StartLimit`. Both will happily spin forever on a config typo, and
neither tells you.

`serve` refuses to start on an unreadable config, which is exactly the case you
want to stay dead and visible. `mirror` is the opposite: a workspace with no
session yet is normal, so it logs and keeps polling rather than exiting, and the
supervisor never sees a failure at all.

If you would rather not have either under a supervisor, run them by hand. The
tool is happy either way.
