class bubble:
    # --- Helper Functions ---
    def wrap_text(text, font, max_width):
        """Wraps text to fit within a specified width."""
        lines = []
        # Handle potential None or empty text
        if not text:
            return [""]
        # Split into paragraphs first to preserve line breaks
        paragraphs = text.split('\n')
        for paragraph in paragraphs:
            words = paragraph.split(' ')
            current_line = []
            while words:
                word = words.pop(0)
                test_line = ' '.join(current_line + [word])
                # Check if the line fits
                if font.size(test_line)[0] <= max_width:
                    current_line.append(word)
                # If the line doesn't fit AND it's not the only word
                elif current_line:
                    lines.append(' '.join(current_line))
                    current_line = [word] # Start new line with the word that didn't fit
                # If the line doesn't fit and it IS the only word (word is too long)
                else:
                    # Simple character-based wrap for overly long words
                    temp_word = ""
                    for char in word:
                        if font.size(temp_word + char)[0] <= max_width:
                            temp_word += char
                        else:
                            lines.append(temp_word)
                            temp_word = char
                    if temp_word: # Add the remainder of the long word
                        lines.append(temp_word)
                    current_line = [] # Reset current line after handling long word
            # Add the last line of the paragraph if it has content
            if current_line:
                lines.append(' '.join(current_line))
            # Add an empty line between paragraphs if the original text had one
            if paragraph != paragraphs[-1]: # Don't add extra space after the last paragraph
                lines.append("") # Add empty string to represent paragraph break
        # Ensure at least one line is returned if text was just whitespace
        if not lines and text.strip() == "":
            return [""]
        elif not lines: # If text was non-empty but resulted in no lines somehow
            return [text] # Return original text as a single line
        return lines
