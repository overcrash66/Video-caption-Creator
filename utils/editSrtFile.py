import re

def center_srt_captions(input_file, output_file):
    # Regular expression to match SRT entries (number, timestamp, and text)
    srt_entry_pattern = re.compile(r"(\d+)\n(\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3})\n((?:.+(?:\n|$))+)")
    
    with open(input_file, "r", encoding="utf-8") as file:
        content = file.read()
    
    # Function to center the text for a single SRT entry
    def center_text(match):
        subtitle_number = match.group(1)
        timestamp = match.group(2)
        text = match.group(3)
        
        # Remove extra newlines and center-align each line of text
        centered_text = "\n".join([f"<center>{line.strip()}</center>" for line in text.strip().split("\n")])
        return f"{subtitle_number}\n{timestamp}\n{centered_text}"
    
    # Apply transformation to all matched SRT entries
    updated_content = srt_entry_pattern.sub(center_text, content)
    
    # Write the updated content to the output file
    with open(output_file, "w", encoding="utf-8") as file:
        file.write(updated_content)

# Example usage
input_srt = "audio-test-translation-edited.srt"  # Replace with the path to your input SRT file
output_srt = "output_centered.srt"  # Replace with the path to your output SRT file
center_srt_captions(input_srt, output_srt)

print(f"Updated SRT file saved as {output_srt}")
