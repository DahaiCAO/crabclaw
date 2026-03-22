"""Lightweight pure-Python BM25 Retriever for Crabclaw."""

import math
from collections import Counter
from typing import Any, Dict, List

class BM25Retriever:
    """A pure-Python implementation of BM25 for lightweight local retrieval."""
    
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.documents: List[Dict[str, Any]] = []
        self.corpus_size = 0
        self.avg_doc_len = 0.0
        self.doc_freqs: Dict[str, int] = {}
        self.idf: Dict[str, float] = {}
        self.doc_len: List[int] = []
        self.doc_tf: List[Dict[str, int]] = []
        
    def _tokenize(self, text: str) -> List[str]:
        """Extremely simple tokenizer. For better CJK support, we split by characters if needed, 
        but here we use a mix of word and char level to keep it dependency-free."""
        # Simple split by whitespace and lowercasing
        text = text.lower()
        import re
        # Extract alphanumeric English words and individual CJK characters
        tokens = re.findall(r'[a-z0-9]+|[\u4e00-\u9fff]', text)
        return tokens

    def add_documents(self, documents: List[Dict[str, Any]]):
        """Add documents. Each doc must be a dict with at least 'content'."""
        self.documents.extend(documents)
        
        # Reset and rebuild index
        self.corpus_size = len(self.documents)
        self.doc_len = []
        self.doc_tf = []
        self.doc_freqs = Counter()
        
        total_len = 0
        for doc in self.documents:
            content = str(doc.get("content", ""))
            tokens = self._tokenize(content)
            self.doc_len.append(len(tokens))
            total_len += len(tokens)
            
            tf = Counter(tokens)
            self.doc_tf.append(tf)
            for term in tf.keys():
                self.doc_freqs[term] += 1
                
        self.avg_doc_len = total_len / max(1, self.corpus_size)
        
        # Calculate IDF
        self.idf = {}
        for term, freq in self.doc_freqs.items():
            # Standard BM25 IDF formula
            self.idf[term] = math.log(1 + (self.corpus_size - freq + 0.5) / (freq + 0.5))

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Search documents matching the query."""
        if not self.documents:
            return []
            
        tokens = self._tokenize(query)
        scores = []
        
        for i in range(self.corpus_size):
            score = 0.0
            doc_len = self.doc_len[i]
            tf = self.doc_tf[i]
            
            for token in tokens:
                if term_freq := tf.get(token, 0):
                    idf = self.idf.get(token, 0.0)
                    # BM25 term score
                    numerator = term_freq * (self.k1 + 1)
                    denominator = term_freq + self.k1 * (1 - self.b + self.b * doc_len / max(1.0, self.avg_doc_len))
                    score += idf * (numerator / denominator)
            
            scores.append((score, i))
            
        # Sort by score descending
        scores.sort(key=lambda x: x[0], reverse=True)
        
        # Return top_k docs with score > 0
        results = []
        for score, idx in scores[:top_k]:
            if score > 0:
                doc_copy = self.documents[idx].copy()
                doc_copy["_score"] = score
                results.append(doc_copy)
                
        return results
