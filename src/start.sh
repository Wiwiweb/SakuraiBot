#!/bin/bash

# Pretty much copy-pasted from reddit-xkcdbot, with slight changes

# Kill if started
export SAKURAIPID=`ps aux | grep '[s]akuraibot.py' | awk '{print($2)}'`

if [ -n $SAKURAIPID ]
  echo "Killing old process "$SAKURAIPID
  then kill $SAKURAIPID
fi

# Update from git
git pull

# Start
nohup python src/sakuraibot.py &
