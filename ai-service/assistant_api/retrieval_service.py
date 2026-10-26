import hashlib
import json
import logging
import re
from collections import defaultdict
from pathlib import Path
from threading import Lock

import jieba
import torch
from qdrant_client import QdrantClient, models
from rank_bm25 import BM25Okapi
from sentence_transformers import CrossEncoder, SentenceTransformer


SERVICE_DIR = Path(__file__).resolve().parents[1]
SOURCE_PATH = SERVICE_DIR / "knowledge" / "booking_rules.md"
INDEX_PATH = SERVICE_DIR / "data" / "vector_index"

EMBEDDING_MODEL = "BAAI/bge-small-zh-v1.5"
RERANK_MODEL = "BAAI/bge-reranker-base"
QUERY_PROMPT = "为这个句子生成表示以用于检索相关文章："

FETCH_K = 3
CANDIDATE_K = 3
RRF_CONSTANT = 60

STOP_WORDS = {
    "的", "了", "吗", "呢", "我", "你",
    "请", "一下", "如何", "怎么", "什么",
}

jieba.setLogLevel(logging.WARNING)


def tokenize(text):
    return [
        word
        for word in jieba.cut_for_search(text.lower())
        if word not in STOP_WORDS
        and re.search(r"[\u4e00-\u9fffa-z0-9]", word)
    ]


def split_sections(text):
    sections = re.split(r"(?m)^##[ \t]+", text)[1:]
    documents = {}
    titles = set()

    for index, section in enumerate(sections, start=1):
        title, separator, body = section.partition("\n")
        title = title.strip()
        body = body.strip()

        if not separator or not title or not body:
            raise ValueError("知识小节的标题或正文为空。")

        if title in titles:
            raise ValueError("知识小节标题重复。")

        content = f"## {title}\n{body}"

        if len(content) > 350:
            raise ValueError(
                f"小节“{title}”过长，请先拆成完整的小节。"
            )

        titles.add(title)
        chunk_id = f"C{index}"

        documents[chunk_id] = {
            "chunk_id": chunk_id,
            "title": title,
            "text": content,
        }

    if not documents:
        raise ValueError("知识文档没有有效的二级标题小节。")

    return documents


class RetrievalService:
    def __init__(self):
        if not torch.cuda.is_available():
            raise RuntimeError("当前服务环境的 CUDA 不可用。")

        text = SOURCE_PATH.read_text(encoding="utf-8-sig")
        self.documents = split_sections(text)
        self.chunk_ids = list(self.documents)

        version_data = {
            "source": SOURCE_PATH.name,
            "text": text,
            "embedding_model": EMBEDDING_MODEL,
            "query_prompt": QUERY_PROMPT,
            "normalize_embeddings": True,
            "splitter": "markdown_h2_v1_max350",
        }

        serialized = json.dumps(
            version_data,
            ensure_ascii=False,
            sort_keys=True,
        )

        self.index_version = hashlib.sha256(
            serialized.encode("utf-8")
        ).hexdigest()

        self.collection_name = f"booking_rules_{self.index_version}"
        self.lock = Lock()

        tokenized = [
            tokenize(self.documents[chunk_id]["text"])
            for chunk_id in self.chunk_ids
        ]

        self.token_sets = [set(tokens) for tokens in tokenized]
        self.bm25 = BM25Okapi(tokenized)

        print("正在加载 GPU 检索模型……")

        self.encoder = SentenceTransformer(
            EMBEDDING_MODEL,
            device="cuda",
            local_files_only=True,
        )

        self.reranker = CrossEncoder(
            RERANK_MODEL,
            device="cuda",
            max_length=512,
            local_files_only=True,
        )

        INDEX_PATH.mkdir(parents=True, exist_ok=True)

        # 路由在线程池中调用。
        # 由下面的 Lock 负责串行访问共享资源。
        self.client = QdrantClient(
            path=str(INDEX_PATH),
            force_disable_check_same_thread=True,
        )

        try:
            self.ensure_index()
        except Exception:
            self.client.close()
            raise

        print("Embedding 设备：", self.encoder.device)
        print("Reranker 设备：", self.reranker.device)
        print("索引版本：", self.index_version[:12])

    def ensure_index(self):
        exists = self.client.collection_exists(
            collection_name=self.collection_name,
        )

        if exists:
            count = self.client.count(
                collection_name=self.collection_name,
                exact=True,
            ).count

            if count == len(self.documents):
                print("当前版本索引已存在，直接复用。")
                return
        else:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(
                    size=self.encoder.get_sentence_embedding_dimension(),
                    distance=models.Distance.COSINE,
                ),
            )

        print("正在写入当前版本的知识索引……")

        vectors = self.encoder.encode(
            [
                self.documents[chunk_id]["text"]
                for chunk_id in self.chunk_ids
            ],
            prompt="",
            normalize_embeddings=True,
            show_progress_bar=False,
        )

        self.client.upsert(
            collection_name=self.collection_name,
            points=[
                models.PointStruct(
                    id=index,
                    vector=vector.tolist(),
                    payload=self.documents[chunk_id],
                )
                for index, (chunk_id, vector) in enumerate(
                    zip(self.chunk_ids, vectors),
                    start=1,
                )
            ],
            wait=True,
        )

        count = self.client.count(
            collection_name=self.collection_name,
            exact=True,
        ).count

        if count != len(self.documents):
            raise RuntimeError("索引片段数量检查失败。")

    def search(self, question, top_k):
        with self.lock:
            return self._search(question, top_k)

    def _search(self, question, top_k):
        vector = self.encoder.encode(
            question,
            prompt=QUERY_PROMPT,
            normalize_embeddings=True,
            show_progress_bar=False,
        )

        points = self.client.query_points(
            collection_name=self.collection_name,
            query=vector.tolist(),
            limit=FETCH_K,
            with_payload=True,
        ).points

        dense_ids = [
            point.payload["chunk_id"]
            for point in points
        ]

        query_tokens = list(dict.fromkeys(tokenize(question)))
        query_set = set(query_tokens)
        lexical_scores = self.bm25.get_scores(query_tokens)

        matched = [
            index
            for index, tokens in enumerate(self.token_sets)
            if query_set.intersection(tokens)
        ]

        lexical_ids = [
            self.chunk_ids[index]
            for index in sorted(
                matched,
                key=lambda index: float(lexical_scores[index]),
                reverse=True,
            )[:FETCH_K]
        ]

        rrf_scores = defaultdict(float)

        for ranking in (dense_ids, lexical_ids):
            for rank, chunk_id in enumerate(ranking, start=1):
                rrf_scores[chunk_id] += 1 / (RRF_CONSTANT + rank)

        candidates = sorted(
            rrf_scores,
            key=lambda chunk_id: rrf_scores[chunk_id],
            reverse=True,
        )[:CANDIDATE_K]

        chunks = []

        if candidates:
            scores = self.reranker.predict(
                [
                    (question, self.documents[chunk_id]["text"])
                    for chunk_id in candidates
                ],
                batch_size=4,
                show_progress_bar=False,
                activation_fn=torch.nn.Identity(),
            )

            ranked = sorted(
                zip(candidates, scores),
                key=lambda item: float(item[1]),
                reverse=True,
            )

            chunks = [
                {
                    **self.documents[chunk_id],
                    "rerank_score": float(score),
                }
                for chunk_id, score in ranked[:top_k]
            ]

        return {
            "source": SOURCE_PATH.name,
            "index_version": self.index_version,
            "device": str(self.encoder.device),
            "chunks": chunks,
        }

    def close(self):
        with self.lock:
            self.client.close()