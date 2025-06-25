# Praat intervalles2wav
#
# for each wav file of a given folder, select corresponding TextGrid file
# for each tier and for each intervalle (!=""), save it as independant wav file in output directory
#
# inspired from Copyright 8.3.2002 Mietta Lennes' praat script (save_labeled_intervals_to_wav_sound_files.praat)
# S. Coulange 2022

form Create wav files from tier
    sentence audio_directory data/
    sentence textgrid_directory pyannote/
    sentence textgrid_extension .pyannote.TextGrid
    sentence output_directory audio/
    real nbTiers 3
    real margin 0.01
    real min_duration 8
endform


# audio_directory$ = "data/"
# textgrid_directory$ = "pyannote/"
# textgrid_extension$ = ".pyannote.TextGrid"
# output_directory$ = "audio/"
# nbTiers = 3
# margin = 0.01
# min_duration = 8 
# # don't save the wav file if shorter than this duration (in seconds)


exclude_empty_labels = 1
start_from = 1
prefix$ = ""
suffix$ = "_"

# Create a Table with no rows for listing each output files with time info (start and end time with margin)
table = Create Table with column names: "table", 0, {"File", "Speaker", "Segment", "Start", "End", "Duration"}

for tier from 1 to nbTiers
    appendInfoLine: "Processing tier n°'tier'"
    # Go through all the sound files, one by one:
    Create Strings as file list... list 'audio_directory$'*.wav
    numberOfFiles = Get number of strings

    for ifile to numberOfFiles
        select Strings list
        fileName$ = Get string... ifile
	fileNameNoExt$ = replace$ (fileName$, ".wav", "", 0)        

        appendInfoLine: "traitement de 'fileName$'..."

        # open Audio folder
        audioPath$ = "'audio_directory$''fileName$'"

        if fileReadable (audioPath$)
            audio = Open long sound file: "'audioPath$'"
            
            # Open corresponding TextGrid
            textgridFile$ = "'textgrid_directory$''fileNameNoExt$''textgrid_extension$'"

            if fileReadable (textgridFile$)
                tg = Read from file: "'textgridFile$'"

                nbTier = Get number of tiers
                appendInfoLine: "   'nbTier' tiers..."
                if tier < nbTier+1
                    appendInfoLine: "   ...continue."
                    selectObject: audio, tg

                    # FROM HERE : MODIFIED Mietta Lennes' PRAAT SCRIPT
                    gridname$ = selected$ ("TextGrid", 1)
                    soundname$ = selected$ ("LongSound", 1)
                    select TextGrid 'gridname$'
                    numberOfIntervals = Get number of intervals: tier
                    
                    appendInfoLine: "    Nb intervalles : 'numberOfIntervals'"
                    
                    end_at = numberOfIntervals

                    # Default values for variables
                    files = 0
                    intervalstart = 0
                    intervalend = 0
                    interval = 1
                    intname$ = ""
                    intervalfile$ = ""
                    endoffile = Get end time

                    
                    for interval from start_from to end_at
                        xxx$ = Get label of interval: tier, interval
                        check = 0
                        
                        if xxx$ = "" and exclude_empty_labels = 1
                            check = 1
                        endif
                        
                        if check = 0
                            files = files + 1
                        endif
                    endfor

                    interval = 1


                    # Loop through all intervals in the selected tier of the TextGrid
                    for interval from start_from to end_at
                        select TextGrid 'gridname$'
                        intname$ = ""
                        intname$ = Get label of interval: tier, interval
			intervalstart = Get start time of interval: tier, interval
			intervalend = Get end time of interval: tier, interval	
			intervalduration = intervalend - intervalstart
                        check = 0

                        if intname$ = "<p:>"
                            check = 1
                        endif
                        if intname$ = "" and exclude_empty_labels = 1
                            check = 1
                        endif
                        if intervalduration < min_duration
                            check = 1
			endif

                        if check = 0
                                if intervalstart > margin
                                    intervalstart = intervalstart - margin
                                else
                                    intervalstart = 0
                                endif
                        
                            
                                if intervalend < endoffile - margin
                                    intervalend = intervalend + margin
                                else
                                    intervalend = endoffile
                                endif
                        
                            select LongSound 'soundname$'
                            Extract part: intervalstart, intervalend, "no"
                            
                            indexnumber = 0
                            intervalfile$ = "'output_directory$'" + "'prefix$'" + "'fileNameNoExt$'" +"_'intname$'"+ "'suffix$''indexnumber'" + ".wav"
                            while fileReadable (intervalfile$)
                                indexnumber = indexnumber + 1
                                intervalfile$ = "'output_directory$'" + "'prefix$'" + "'fileNameNoExt$'" +"_'intname$'"+ "'suffix$''indexnumber'" + ".wav"
                            endwhile
                            Write to WAV file: "'intervalfile$'"
                            Remove
                            
                            ################
                            # Write segment info in the table "File Speaker Segment Start End Duration"
                            selectObject: table
                            Append row
                            current_row = Get number of rows
                            # Insert your values
                            Set string value:  current_row, "File", "'fileName$'"
                            Set string value:  current_row, "Speaker", "'intname$'"
                            Set string value: current_row, "Segment", "'prefix$'" + "'fileNameNoExt$'" +"_'intname$'"+ "'suffix$''indexnumber'"
                            Set numeric value: current_row, "Start", intervalstart
                            Set numeric value: current_row, "End", intervalend 
                            Set numeric value: current_row, "Duration", intervalend - intervalstart
                            ##################
                            


                        endif
                    endfor
                endif
                selectObject: audio, tg
                Remove
            endif
        endif
    endfor
endfor

# Save the table
selectObject: table
Save as semicolon-separated file: "'textgrid_directory$'" + "segmentFromPyannote_timeInfo.csv"
removeObject(table)