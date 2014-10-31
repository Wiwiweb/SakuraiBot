#!/bin/bash

# Pretty much copy-pasted from reddit-xkcdbot, with slight changes

# Kill statuscheck
export STATUSPID=`ps aux | grep 'statuscheck.py' | grep -v grep | awk '{print($2)}'`
if [ -n "$STATUSPID" ]; then
  echo "Killing old statuscheck "$STATUSPID"."
  kill $STATUSPID
fi


# Kill if started
export SAKURAIPID=`ps aux | grep '__init__.py' | grep -v grep | awk '{print($2)}'`
if [ -n "$SAKURAIPID" ]; then
  echo "Killing old process "$SAKURAIPID"."
  kill $SAKURAIPID
fi

# Update from git
echo "Pulling latest git version"
git pull

# Start
echo "Starting"
cd src
nohup python3 __init__.py --miiverse >../nohup.out 2>&1 &
disown
sleep 1
export SAKURAIPID=`ps aux | grep '__init__.py' | grep -v grep | awk '{print($2)}'`
if [ -n "$SAKURAIPID" ]; then
  echo "Running correctly."
else
  echo "ERROR: Script stopped."
fi

# Start statuscheck
echo "Starting statuscheck"
nohup python3 statuscheck.py >../nohup.out 2>&1 &
disown
sleep 1
export STATUSPID=`ps aux | grep 'statuscheck.py' | grep -v grep | awk '{print($2)}'`
if [ -n "$STATUSPID" ]; then
  echo "Statuscheck running correctly."
else
  echo "ERROR: Statuscheck stopped."
fi


