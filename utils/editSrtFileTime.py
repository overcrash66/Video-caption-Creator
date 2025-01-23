import sys

def timecode_to_ms(tc):
    """Convert timecode to milliseconds."""
    clean_tc = tc.strip().replace('\r', '').replace('\u202f', ' ').replace('\ufeff', '')
    hours, mins, rest = clean_tc.split(':', 2)
    if ',' in rest:
        secs, ms = rest.split(',')
    elif '.' in rest:
        secs, ms = rest.split('.')
    else:
        secs, ms = rest, '000'
    return int(hours)*3600000 + int(mins)*60000 + int(secs)*1000 + int(ms.ljust(3, '0')[:3])

def ms_to_timecode(ms):
    """Convert milliseconds to timecode."""
    ms = max(ms, 0)
    hours, ms = divmod(ms, 3600000)
    mins, ms = divmod(ms, 60000)
    secs, ms = divmod(ms, 1000)
    return f"{hours:02}:{mins:02}:{secs:02},{ms:03}"

def process_srt(input_file, delay_ms, output_file):
    with open(input_file, 'r', encoding='utf-8-sig') as f:
        content = f.read().replace('\r\n', '\n').replace('\r', '\n')  # Normalize line endings

    blocks = [b.strip() for b in content.split('\n\n') if b.strip()]
    processed = []
    previous_end_time = None

    for block in blocks:
        lines = [l.strip() for l in block.split('\n')]
        if len(lines) < 3:
            processed.append(block)
            continue

        try:
            # Extract caption number, time line, and content
            header = lines[0]
            time_line = lines[1]
            content = '\n'.join(lines[2:])

            if '-->' not in time_line:
                processed.append(block)
                continue

            # Parse timings
            start_str, end_str = time_line.split('-->')
            orig_start = timecode_to_ms(start_str)
            orig_end = timecode_to_ms(end_str)
            duration = orig_end - orig_start

            # Adjust start time and ensure no gap
            if previous_end_time is not None:
                new_start = previous_end_time  # Start time of this caption is the end time of the previous one
            else:
                new_start = max(orig_start + delay_ms, 0)

            # Ensure the end time is consistent with the duration
            new_end = new_start + duration
            previous_end_time = new_end  # Update for the next block

            # Format new timecodes
            new_block = [
                header,
                f"{ms_to_timecode(new_start)} --> {ms_to_timecode(new_end)}",
                content
            ]
            processed.append('\n'.join(new_block))
        except Exception as e:
            processed.append(block)

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n\n'.join(processed))

if __name__ == '__main__':
    if len(sys.argv) != 4:
        print("Usage: python editSrtFileTime.py <input.srt> <delay_ms> <output.srt>")
        sys.exit(1)
    
    process_srt(sys.argv[1], int(sys.argv[2]), sys.argv[3])
