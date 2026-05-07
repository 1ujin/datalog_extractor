rem @echo off
rem 编译资源文件
start pyrcc5 -o ./src/resource.py ./resource/resource.qrc
rem 生成可执行文件
start pyinstaller ./datalog_extractor.spec
