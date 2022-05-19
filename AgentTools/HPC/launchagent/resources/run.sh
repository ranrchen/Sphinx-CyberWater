# Judge Model Source Type, Source Code or Executable Program
arg=$1
exe_str=$2
obj_str=$3

if [ -z $exe_str ]
then
  echo "Compile Model Source Code {$obj_str}"
  cd $obj_str || exit
  make CC=gcc CFLAGS="-std=c99 -I ."
  if [ $? -ne 0 ]
  then
    echo "Compile VIC failed"
    exit 1
  fi
  echo "Running Executable Program $obj_str"
  cd ..
  ./$obj_str/$obj_str $arg 1>./$obj_str.log 2>./$obj_str.err
else
  echo "Running Executable Program $exe_str"
  ./$exe_str $arg 1>./$exe_str.log 2>./$exe_str.err
fi

echo "VIC returned $?"
echo "Now exiting..."