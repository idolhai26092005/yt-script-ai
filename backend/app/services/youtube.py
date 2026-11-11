import re
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound, VideoUnavailable

# Regex to extract YouTube video ID from various URL formats
YOUTUBE_REGEX = r'(?:youtube\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?|shorts)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})'

def extract_video_id(url: str) -> str | None:
    match = re.search(YOUTUBE_REGEX, url)
    if match:
        return match.group(1)
    
    # Check if the URL is actually just an 11-char ID
    clean_url = url.strip()
    if len(clean_url) == 11 and re.match(r'^[a-zA-Z0-9_-]{11}$', clean_url):
        return clean_url
        
    return None

def compress_transcript(text: str) -> str:
    """
    Compresses transcript text by:
    1. Removing timestamps like [00:00:00] or (00:00:00)
    2. Removing filler words (um, uh, like, you know, etc.)
    3. Normalizing whitespace
    4. Removing consecutively repeated lines/sentences
    """
    # 1. Remove timestamps
    text = re.sub(r'\[\d{1,2}:\d{2}(?::\d{2})?\]', '', text)
    text = re.sub(r'\(\d{1,2}:\d{2}(?::\d{2})?\)', '', text)
    
    # 2. Remove filler words (case-insensitive, matching word boundaries)
    fillers = [r'\bum\b', r'\buh\b', r'\blike\b', r'\byou know\b', r'\bI mean\b', 
               r'\bsort of\b', r'\bkind of\b', r'\bbasically\b', r'\bactually\b', r'\bliterally\b']
    for filler in fillers:
        text = re.sub(filler, '', text, flags=re.IGNORECASE)
        
    # 3. Clean up duplicate/consecutive commas and leading/trailing spaces around punctuation
    text = re.sub(r',(\s*,)+', ',', text)
    text = re.sub(r'\s+,', ',', text)
    
    # 4. Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    # 5. Remove consecutive duplicate sentences
    sentences = re.split(r'(?<=[.!?])\s+', text)
    deduped_sentences = []
    prev_sentence = None
    for s in sentences:
        s_clean = s.strip()
        if not s_clean:
            continue
        if s_clean.lower() != prev_sentence:
            deduped_sentences.append(s_clean)
            prev_sentence = s_clean.lower()
    
    return " ".join(deduped_sentences)


class YouTubeService:
    @staticmethod
    def get_transcript(video_id: str) -> tuple[str, list[dict]]:
        """
        Fetches transcript for the given video_id.
        Prioritizes English (en) and Vietnamese (vi).
        Returns a tuple (full_transcript_text, segments_list).
        """
        try:
            from youtube_transcript_api.proxies import GenericProxyConfig
            
            from app.core.config import settings
            proxy_url = settings.PROXY_URL
            proxy_config = None
            if proxy_url:
                proxy_url_clean = proxy_url.strip('\'"').strip()
                if proxy_url_clean:
                    proxy_config = GenericProxyConfig(
                        http_url=proxy_url_clean,
                        https_url=proxy_url_clean
                    )

            # Attempt to fetch and translate
            api = YouTubeTranscriptApi(proxy_config=proxy_config)
            transcripts = api.list(video_id)
            
            try:
                # Prioritize Vietnamese and English
                transcript = transcripts.find_transcript(['vi', 'en'])
            except NoTranscriptFound:
                # Fallback to any other language
                all_transcripts = list(transcripts)
                if not all_transcripts:
                    raise NoTranscriptFound(video_id, ['vi', 'en'], transcripts)
                transcript = all_transcripts[0]

            # Translate if language is not vi or en
            if transcript.language_code not in ['vi', 'en']:
                try:
                    transcript = transcript.translate('vi')
                except Exception:
                    try:
                        transcript = transcript.translate('en')
                    except Exception:
                        pass

            transcript_list = transcript.fetch()
            
            # Combine transcript segments into full text
            full_text = " ".join([segment.text for segment in transcript_list])
            # Normalize whitespace
            full_text = re.sub(r'\s+', ' ', full_text).strip()
            
            return full_text, transcript_list
            
        except TranscriptsDisabled:
            raise RuntimeError("Phụ đề đã bị tắt cho video này.")
        except NoTranscriptFound:
            raise RuntimeError("Không tìm thấy phụ đề phù hợp (tiếng Anh hoặc tiếng Việt).")
        except VideoUnavailable:
            raise RuntimeError("Video không khả dụng hoặc bị khóa (private).")
        except Exception as e:
            raise RuntimeError(f"Lỗi lấy phụ đề từ YouTube: {str(e)}")

    @staticmethod
    def chunk_transcript(full_text: str, chunk_size: int = 3000, overlap: int = 200) -> list[str]:
        """
        Chunks the transcript based on word count, aligning boundaries to sentence ends (. ! ?).
        If total words < 3000, returns the entire transcript as a single chunk.
        """
        # Check if transcript has sentence boundaries
        if not re.search(r'[.!?]', full_text) or len(re.split(r'(?<=[.!?])\s+', full_text)) <= 1:
            # Fallback to word-based chunking
            words = full_text.split()
            total_words = len(words)
            if total_words < 3000:
                return [full_text]
            chunks = []
            start = 0
            while start < total_words:
                end = min(start + chunk_size, total_words)
                chunk_words = words[start:end]
                chunks.append(" ".join(chunk_words))
                if end >= total_words:
                    break
                start = end - overlap
                if start >= end:
                    start = end - 1
            return chunks

        sentences = re.split(r'(?<=[.!?])\s+', full_text)
        words = full_text.split()
        total_words = len(words)
        
        if total_words < 3000:
            return [full_text]
            
        chunks = []
        current_chunk = []
        current_word_count = 0
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            sentence_words = sentence.split()
            sentence_word_count = len(sentence_words)
            
            if current_word_count + sentence_word_count > chunk_size and current_chunk:
                chunks.append(" ".join(current_chunk))
                # Generate overlap from the end of current_chunk
                overlap_words = []
                overlap_sentences = []
                for s in reversed(current_chunk):
                    s_words = s.split()
                    if len(overlap_words) + len(s_words) <= overlap:
                        overlap_words = s_words + overlap_words
                        overlap_sentences.insert(0, s)
                    else:
                        break
                current_chunk = overlap_sentences
                current_word_count = sum(len(s.split()) for s in current_chunk)
                
            current_chunk.append(sentence)
            current_word_count += sentence_word_count
            
        if current_chunk:
            chunks.append(" ".join(current_chunk))
            
        return chunks
