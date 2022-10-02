#!/bin/bash
if [ "$1" = "--cleanup" ]; then
   echo "cleaning up temporary COPY files"
   rm -f *-COPY.yaml
   exit 0
fi

function step() {
   fromfile="${2:?}.yaml"
   tofile="${1:?}-${2:?}-COPY.yaml"
   echo -n "copying ${fromfile} (to ${tofile})"
   cp ../../common/${fromfile} ${tofile}
   # t=branch to end if previous substitution was successful
   # q=set exit code to 5
   # OPERATOR_TAG has /'s and :'s, so need to use a different character
   sed -e "s&%%OPERATOR_TAG%%&${OPERATOR_TAG}&g" -i '' ${tofile}
   if diff ../../common/${fromfile} ${tofile}>/dev/null; then
      echo ' - done'
   else
      echo -n ', setting '
      grep 'image:' ${tofile} || echo "(no image found)"
   fi
   echo -e '\n# DO NOT MODIFY. Master in tests/common' >> ${tofile}
}

function local_step() {
   file="${1:?}-${2:?}.yaml"
   if [ ! -f "$file" ]; then
      echo "update-steps.sh identifies step ${1}, but ${1:?}-${2:?}.yaml is missing" >&2
      exit 1
   fi
}