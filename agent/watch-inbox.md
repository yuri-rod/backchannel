---
description: Watch the backchannel inbox and answer whatever arrives
---

Bring the bridge up and stay on it:

1. Start the two processes if they are not already running:

   ```
   backchannel serve &
   backchannel mirror &
   ```

2. Print the chat URL and give it to me, and nothing else from it:

   ```
   backchannel url
   ```

3. Watch the inbox for new files, one line per arrival, skipping the partial
   `.upload-` temporaries:

   ```
   cd "${BACKCHANNEL_SHARE_ROOT:-$HOME/.backchannel/share}/inbox" || exit 1
   seen=$(/bin/ls -1A 2>/dev/null | grep -v '^\.upload-' | sort)
   while true; do
     sleep 3
     cur=$(/bin/ls -1A 2>/dev/null | grep -v '^\.upload-' | sort)
     comm -13 <(printf '%s\n' "$seen") <(printf '%s\n' "$cur") | while IFS= read -r f; do
       [ -n "$f" ] && echo "inbox: $f"
     done
     seen=$cur
   done
   ```

When a file shows up, read it and act on it straight away, without waiting for
me to say anything. A `pasted-*.txt` file is a message I typed on my phone;
anything else is a file I wanted you to have.

The URL is public and the token is the only thing protecting it. Do not repeat
the token anywhere except in your answer to me.
