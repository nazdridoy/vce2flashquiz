import sys
import os
import re
import argparse
import base64
from pathlib import Path
from pypdf import PdfReader
from pypdf.generic import ContentStream

def get_image_base64_from_data(data, name):
    """Converts raw image data to a base64 string."""
    try:
        # Check for common image signatures
        if data.startswith(b'\xff\xd8'): ext = 'jpg'
        elif data.startswith(b'\x89PNG'): ext = 'png'
        elif data.startswith(b'GIF'): ext = 'gif'
        else:
            ext = name.split('.')[-1].lower()
            if ext not in ['png', 'jpg', 'jpeg', 'gif']:
                ext = 'png'
        
        b64_data = base64.b64encode(data).decode('utf-8')
        return f"data:image/{ext};base64,{b64_data}"
    except Exception:
        return None

def extract_all_image_occurrences(pdf_path):
    """Extracts images in the exact order they appear in the content stream."""
    reader = PdfReader(pdf_path)
    all_occurrences = []
    
    for i, page in enumerate(reader.pages):
        xobjects = page.get('/Resources', {}).get('/XObject', {})
        images = {}
        for name, obj in xobjects.items():
            obj = obj.get_object()
            if obj.get('/Subtype') == '/Image':
                images[name] = obj
        
        try:
            contents = page.get_contents()
            if contents is not None:
                # ContentStream constructor expects (container, pdf)
                stream = ContentStream(contents, reader)
                for operands, operator in stream.operations:
                    if operator == b'Do':
                        name = operands[0] # e.g. "/Image1"
                        if name in images:
                            obj = images[name]
                            data = obj.get_data()
                            b64 = get_image_base64_from_data(data, name)
                            if b64:
                                all_occurrences.append({'page': i, 'b64': b64})
        except Exception as e:
            print(f"Warning: Failed to parse Page {i+1} stream: {e}", file=sys.stderr)
    
    return all_occurrences

def parse_vce_pdf(pdf_path):
    """Extracts text and images from a VCE PDF and converts to Flashquiz format."""
    reader = PdfReader(pdf_path)
    all_images_list = extract_all_image_occurrences(pdf_path)
    
    full_text = ""
    page_offsets = []
    current_offset = 0
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        text += "\n"
        page_offsets.append((current_offset, i))
        full_text += text
        current_offset += len(text)

    markers = list(re.finditer(r'QUESTION\s+\d+', full_text))
    questions = []
    quiz_title = "VCE Quiz"
    
    if markers:
        header = full_text[:markers[0].start()].strip()
        if header:
            lines = header.split('\n')
            if lines:
                quiz_title = lines[0].strip()

    last_image_idx_used = -1
    
    for i, match in enumerate(markers):
        q_start = match.start()
        q_end = markers[i+1].start() if i+1 < len(markers) else len(full_text)
        part = full_text[q_start:q_end]
        
        q_start_page = 0
        q_end_page = 0
        for offset, page_idx in page_offsets:
            if q_start >= offset: q_start_page = page_idx
            if q_end >= offset: q_end_page = page_idx
        
        lines = [line.strip() for line in part.strip().split('\n') if line.strip()]
        if not lines: continue
            
        first_line = lines[0]
        first_line_clean = re.sub(r'^QUESTION\s+\d+\s*', '', first_line).strip()
        if first_line_clean: lines[0] = first_line_clean
        else: lines = lines[1:]

        question_text_lines = []
        options = []
        correct_answer_str = ""
        parsing_options = False
        
        for line in lines:
            if re.match(r'^[A-Z]\.', line):
                parsing_options = True
                options.append(line)
            elif "Correct Answer:" in line:
                correct_answer_str = line.split("Correct Answer:")[1].strip()
                parsing_options = False
            elif not parsing_options:
                question_text_lines.append(line)
            else:
                if options: options[-1] += " " + line
                else: question_text_lines.append(line)
        
        if not question_text_lines or not correct_answer_str: continue
            
        q_text = " ".join(question_text_lines)
        
        if "exhibit" in q_text.lower():
            images_in_span_indices = [
                idx for idx, img in enumerate(all_images_list)
                if q_start_page <= img['page'] <= q_end_page
            ]
            
            assigned_images = []
            seen_b64 = set()
            for idx in images_in_span_indices:
                if idx > last_image_idx_used:
                    b64 = all_images_list[idx]['b64']
                    if b64 not in seen_b64:
                        assigned_images.append(b64)
                        seen_b64.add(b64)
                    last_image_idx_used = idx
            
            if not assigned_images and images_in_span_indices:
                # Fallback: if no new images, use the last unique one in the span
                # This handles cases where multiple questions refer to the same exhibit page
                b64 = all_images_list[images_in_span_indices[-1]]['b64']
                assigned_images.append(b64)
            
            for b64 in assigned_images:
                q_text += f"\n\n![Exhibit]({b64})"
                
        # Parse answers
        answers = [a.lower() for a in re.findall(r'[A-Z]', correct_answer_str)]
        
        is_tf = False
        if len(options) == 2:
            opt_texts = []
            for opt in options:
                m = re.match(r'^[A-Z]\.\s*(.*)', opt)
                if m:
                    t = m.group(1).strip().lower()
                    opt_texts.append(t)
            if "true" in opt_texts and "false" in opt_texts:
                is_tf = True

        formatted_options = []
        for opt in options:
            m = re.match(r'^([A-Z])\.\s*(.*)', opt)
            if m:
                letter = m.group(1).lower()
                text = m.group(2).strip()
                formatted_options.append(f"{letter}) {text}")

        if is_tf:
            q_type = "@tf"
            ans_letter = answers[0] if answers else 'a'
            final_answer = "true" if ans_letter == 'a' else "false"
        else:
            q_type = "@mc" if len(answers) == 1 else "@sata"
            final_answer = ", ".join(answers)

        questions.append({
            'type': q_type,
            'text': q_text,
            'options': formatted_options if not is_tf else [],
            'answer': final_answer
        })
        
    return quiz_title, questions

def format_flashquiz(title, questions):
    """Formats the output into Flashquiz markdown with Inline Base64 exhibits."""
    output = []
    output.append("---")
    output.append(f'quiz-title: "{title}"')
    output.append("time-limit: 0")
    output.append("pass-score: 80")
    output.append("shuffle: true")
    output.append("show-answer: true")
    output.append('exam-range: "-"')
    output.append("---")
    output.append("")
    
    for i, q in enumerate(questions, 1):
        output.append(f"{q['type']} {i}) {q['text']}")
        if q['options']:
            for opt in q['options']:
                output.append(opt)
        output.append(f"= {q['answer']}")
        output.append("")
            
    return "\n".join(output)

def process_pdf(pdf_path, output_path=None):
    """Process a single PDF file and optionally write to output file."""
    title, questions = parse_vce_pdf(pdf_path)
    output = format_flashquiz(title, questions)
    
    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(output)
        return True
    else:
        print(output)
        return True

def main():
    parser = argparse.ArgumentParser(
        description="Convert VCE PDF to Flashquiz with inline Base64 images.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s input.pdf              Convert single PDF, output to stdout
  %(prog)s /path/to/pdfs/         Convert all PDFs in directory, create .md files
"""
    )
    parser.add_argument(
        "input_path", 
        help="Path to a VCE PDF file or a directory containing PDF files."
    )
    args = parser.parse_args()
    
    input_path = Path(args.input_path)
    
    if input_path.is_dir():
        # Process all PDFs in directory
        pdf_files = list(input_path.glob("*.pdf")) + list(input_path.glob("*.PDF"))
        
        if not pdf_files:
            print(f"Error: No PDF files found in '{input_path}'", file=sys.stderr)
            sys.exit(1)
        
        print(f"Found {len(pdf_files)} PDF file(s) to process...", file=sys.stderr)
        
        for pdf_file in sorted(pdf_files):
            output_file = pdf_file.with_suffix(".md")
            try:
                process_pdf(str(pdf_file), str(output_file))
                print(f"✓ Created: {output_file.name}", file=sys.stderr)
            except Exception as e:
                print(f"✗ Failed: {pdf_file.name} - {e}", file=sys.stderr)
        
        print(f"\nDone! Processed {len(pdf_files)} file(s).", file=sys.stderr)
    
    elif input_path.is_file():
        # Process single PDF file
        if not str(input_path).lower().endswith(".pdf"):
            print("Error: Only PDF files are supported.", file=sys.stderr)
            sys.exit(1)
        
        title, questions = parse_vce_pdf(str(input_path))
        print(format_flashquiz(title, questions))
    
    else:
        print(f"Error: '{input_path}' is not a valid file or directory.", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()

