import sys, os
import time
import re

def timecode_to_ms(tc):
    """Convert timecode to milliseconds."""
    clean_tc = tc.strip().replace('\r', '').replace('\u202f', ' ').replace('\ufeff', '')
    try:
        hours, mins, rest = clean_tc.split(':', 2)
        if ',' in rest:
            secs, ms = rest.split(',')
        elif '.' in rest:
            secs, ms = rest.split('.')
        else:
            secs, ms = rest, '000'
        
        # Validate time components
        if not (0 <= int(hours) < 24 and 0 <= int(mins) < 60 and 0 <= int(secs) < 60):
            raise ValueError("Invalid timecode format: hours, minutes, or seconds out of range")
        
        return int(hours)*3600000 + int(mins)*60000 + int(secs)*1000 + int(ms.ljust(3, '0')[:3])
    except Exception as e:
        raise ValueError(f"Invalid timecode format: {tc}") from e

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
                new_start = max(previous_end_time, orig_start + delay_ms)
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
            print(f"Error processing block: {block}\nError: {e}")
            processed.append(block)

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n\n'.join(processed))
    
    #temp_file = f"{output_file}.bak"
    #os.replace(output_file, temp_file)   
    #clean_srt_file(temp_file, output_file)  

def clean_srt_file(input_path: str, output_path: str) -> None:
    """
    Clean an SRT file by removing invalid or empty subtitle entries
    and fixing formatting issues.
    """
    with open(input_path, "r", encoding="utf-8") as file:
        lines = file.readlines()

    cleaned_lines = []
    buffer = []
    for line in lines:
        line = line.strip()
        if re.match(r"^\d+$", line):  # Entry number
            if buffer:  # Check if previous entry is valid
                cleaned_lines.extend(buffer)
                buffer = []
            buffer.append(line)
        elif re.match(r"^\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}$", line):  # Timestamp
            if buffer and not re.match(r"^\d+$", buffer[-1]):
                buffer.pop()  # Remove invalid entry
            buffer.append(line)
        elif line:  # Subtitle text
            buffer.append(line)
        elif buffer:  # End of an entry
            cleaned_lines.extend(buffer)
            buffer = []

    # Add last buffered entry if valid
    if buffer:
        cleaned_lines.extend(buffer)

    # Write cleaned lines to the output file
    with open(output_path, "w", encoding="utf-8") as file:
        for line in cleaned_lines:
            file.write(line + "\n")


if __name__ == '__main__':
    if len(sys.argv) != 4:
        print("Usage: python editSrtFileTime.py <input.srt> <delay_ms> <output.srt>")
        print("Example: python editSrtFileTime.py input.srt 500 output.srt")
        sys.exit(1)
    
    try:
        process_srt(sys.argv[1], int(sys.argv[2]), sys.argv[3])

        # Example usage
        #clean_srt_file("input.srt", "cleaned_output.srt")
    except Exception as e:
        print(f"Script Error: {str(e)}")
        sys.exit(1)