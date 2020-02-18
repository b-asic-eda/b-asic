#! bin/sh
for n in `find . -name "*.py"`
do
  python $n
done