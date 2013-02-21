#!/bin/bash
set -e
SOURCE_MARC=$1
if [[ "$SOURCE_MARC" == "" ]]; then
    echo "Usage $(basename $0) SOURCE_MARC"
    exit
fi

SOURCE_MARC=$(cd $(dirname $SOURCE_MARC); pwd)/$(basename $SOURCE_MARC)

SCRIPT_DIR=$(dirname $0)
cd $SCRIPT_DIR
WHELKS_BUILD=../whelk-core/build
java -cp $WHELKS_BUILD/classes/main/:$WHELKS_BUILD/libs/whelk-core.jar se.kb.libris.conch.converter.MarcJSONConverter $SOURCE_MARC
