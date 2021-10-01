#!/bin/bash
if [ "$1" = "--cleanup" ]; then
   echo "cleaning up temporary files"
   rm -f *-COPY.yaml
   exit 0
fi

function step() {
   fromfile="${2:?}.yaml"
   tofile="${1:?}-${2:?}-COPY.yaml"
   cp ../../common/${fromfile} ${tofile}
   echo -e '\n# DO NOT MODIFY. Master in tests/common' >> ${tofile}
}
