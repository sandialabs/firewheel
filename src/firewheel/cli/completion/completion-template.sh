#!/bin/bash

# This script provides tab completion for FIREWHEEL from Bash or ZSH (non-interactive mode)
# It iterates over the FIREWHEEL Helpers and adds them to the completion list.
# It parses `firewheel_cli.py` to get FIREWHEEL commands.
# It iterates over available model components if current command is ``firewheel experiment``.
# To enable this script, it should be stored at `/usr/share/bash-completion/completions/firewheel` or
# it can be sourced directly.


#######################################
# Adds tab completion for all model components if the command is `firewheel experiment`.
# To accomplish this, it iterates over model components to add them to the completion list
#######################################
function search_model_components() {
    completion_mcs=($($SHELL -c "
        if [ -n \"$fw_venv\" ]; then
            . \"$fw_venv/bin/activate\";
        fi;
        $python_bin -m firewheel.cli.completion.get_model_component_names
    " 2>/dev/null))
}

#######################################
# Provides some help for optimizing when we iterate over model components.
# If we don't have cached model components, we iterate.
# If the total size of all model component repositories has changed, we iterate.
#######################################
function complete_model_components() {
    if [[ -z $completion_mcs ]];
    then
        search_model_components
    else
        mc_size=$($SHELL -c "
            if [ -n \"$fw_venv\" ]; then
                . \"$fw_venv/bin/activate\";
            fi;
            $python_bin -m firewheel.cli.completion.get_total_model_components_size
        ")
        if [[ $mc_size != $cached_mc_size ]];
        then
            cached_mc_size=$mc_size
            search_model_components
        fi
    fi

    for mc in ${completion_mcs[@]};
    do
        WORD_LIST+=( $mc )
    done
}

#######################################
# Helper function for joining an array
#######################################
function join_by() {
    local IFS="$1";
    shift;
    echo "$*";
}

#######################################
# Helper function for testing if value is in array
#######################################
function array_contains() {
    local seeking=$1; shift
    local in=1
    for element;
    do
        if [[ $element == "$seeking" ]];
        then
            in=0
            break
        fi
    done
    return $in
}

#######################################
# The primary function used for completion.
#######################################
function _fw_complete() {
    # These will be automatically set using (Jinja template variables)
    fw_package_dir="{{ fw_package_dir }}"
    fw_venv="{{ fw_venv }}"
    python_bin="{{ python_bin }}"

    # Get the currently completing word
    local CWORD=${COMP_WORDS[COMP_CWORD]}

    # This is our word list (in a bash array for convenience)
    local WORD_LIST=()

    base_path="$fw_package_dir/cli/helpers/"

    if [[ $COMP_CWORD == 1 ]];
    then
        # Iterate over the top level helpers, could be files or directories
        for file_or_dir in `ls $base_path`;
        do
            # Remove a trailing slash, it makes it easier to read options
            file_or_dir=${file_or_dir%/}
            WORD_LIST+=( "$file_or_dir" )
        done

        # Add FIREWHEEL commands (as opposed to helpers)
        # This syntax will take the printed python list and convert to bash array
        # Need to execute in a new shell so to only activate venv temporarily
        fw_cmds=($($SHELL -c "
            if [ -n \"$fw_venv\" ]; then
                . \"$fw_venv/bin/activate\";
            fi;
            $python_bin -m firewheel.cli.completion.get_available_cli_commands
        "))
        for cmd in ${fw_cmds[@]};
        do
            WORD_LIST+=( $cmd )
        done

    else
        if [[ ${COMP_WORDS[1]} == "experiment" ]];
        then
            # Make sure fetching model component is done
            WORD_LIST=()
            complete_model_components
        elif [[ ${COMP_WORDS[1]} == "config" && $COMP_CWORD == 2 ]];
        then
            # Currently completing word is a command, not a helper
            if [[ ${COMP_WORDS[1]} == "config" && $COMP_CWORD == 2 ]];
            then
                WORD_LIST=( "get" "set" )
            fi
        else
            # Create the path based on what has already been completed
            local helper_path=`join_by / ${COMP_WORDS[@]:1}`
            helper_path=$base_path/$helper_path
            if [[ -f $helper_path ]];
            then
                WORD_LIST=()
            else
                # Don't run ls with the currently completing partial word, it'll cause an error
                if ! ls $helper_path > /dev/null 2>&1;
                then
                    local c_words_len=${#COMP_WORDS[@]}
                    c_words_len=$(expr $c_words_len - 2)
                    helper_path=`join_by / ${COMP_WORDS[@]:1:$c_words_len}`
                    helper_path=$base_path/$helper_path
                fi
                local files=`ls $helper_path 2> /dev/null`
                if [[ -f $files || $helper_path -ef $base_path ]];
                then
                    WORD_LIST=()
                else
                    for file_or_dir in ${files[@]};
                    do
                        file_or_dir=${file_or_dir%/}
                        WORD_LIST+=( "$file_or_dir" )
                    done
                fi
            fi
        fi
    fi

    # Commands below depend on this IFS
    local IFS=$'\n'

    # Filter our candidates
    CANDIDATES=($(compgen -W "${WORD_LIST[*]}" -- "$CWORD"))

    # Correctly set our candidates to COMPREPLY
    if [ ${#CANDIDATES[*]} -eq 0 ]; then
        COMPREPLY=()
    else
        COMPREPLY=($(printf '%q\n' "${CANDIDATES[@]}"))
    fi
}

if [[ $SHELL == *"zsh"* ]];
then
    autoload bashcompinit
    bashcompinit
fi
complete -o bashdefault -o default -F _fw_complete firewheel
