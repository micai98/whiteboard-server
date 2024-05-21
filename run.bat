@echo off
:a
title Whiteboard Server
python -m wbserver 0.0.0.0 3001 http://localhost:3000

echo.
echo.
echo RESTARTING - - - - 

goto a
