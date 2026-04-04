@echo off
C:\Python39\python.exe -m PyInstaller --onedir --windowed --name BongoBass --add-data "img;img" --distpath . bongo_cat.pyw
echo Done! Your build is in BongoBass\
pause