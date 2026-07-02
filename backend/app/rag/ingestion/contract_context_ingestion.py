from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from time import sleep

from app.core.wikipedia_rag_scraper import scrape_wikipedia_for_rag

@dataclass(frozen=True)
class WikipediaTopic:
    label: str
    query: str


WIKIPEDIA_TOPICS = [
    WikipediaTopic("contratos", "contrato direito civil obrigações cláusulas"),
    WikipediaTopic("obrigacoes", "direito das obrigações contrato prestação inadimplemento"),
    WikipediaTopic("boa_fe", "boa-fé objetiva contrato direito civil"),
    WikipediaTopic("inadimplemento", "inadimplemento mora obrigação contrato"),
    WikipediaTopic("responsabilidade", "responsabilidade civil contratual dano indenização"),
    WikipediaTopic("clausula_penal", "cláusula penal contrato multa direito civil"),
    WikipediaTopic("contrato_adesao", "contrato de adesão cláusulas abusivas consumidor"),
    WikipediaTopic("consumidor", "Código de Defesa do Consumidor contrato cláusulas abusivas"),
    WikipediaTopic("privacidade", "Lei Geral de Proteção de Dados contrato dados pessoais"),
    WikipediaTopic("arbitragem", "arbitragem mediação resolução de conflitos contrato"),
    WikipediaTopic("rescisao", "rescisão contratual resolução contrato direito civil"),
    WikipediaTopic("garantias", "garantia contratual vício redibitório evicção"),
]


CONTRACT_REVIEW_SENTENCES = [
    "Ao revisar um contrato, verifique se as partes estão qualificadas de forma completa, incluindo nome, documento, endereço, representante legal e poderes de representação.",
    "Um bom contrato deve declarar objeto, escopo e finalidade com precisão, evitando termos vagos que permitam interpretações incompatíveis entre as partes.",
    "Cláusulas de obrigação devem indicar quem deve fazer, o que deve ser feito, prazo, forma de cumprimento, critérios de aceite e consequência pelo descumprimento.",
    "Prazos contratuais devem ser consistentes entre si e indicar data de início, data de término, condições de renovação e hipóteses de prorrogação.",
    "Valores, reajustes, multas, juros, tributos e forma de pagamento devem estar descritos com clareza para reduzir disputas financeiras.",
    "Cláusulas de multa devem ser proporcionais ao risco e compatíveis com a obrigação principal, evitando penalidades excessivas ou ambíguas.",
    "A revisão deve identificar ausência de matriz de responsabilidades, especialmente em contratos com entregas, integrações, dados, terceiros ou etapas sucessivas.",
    "Cláusulas de rescisão devem prever hipóteses de término por conveniência, por justa causa, por inadimplemento, por caso fortuito e por força maior.",
    "A cláusula de inadimplemento deve prever notificação, prazo de cura, consequências, suspensão de obrigações e preservação de direitos já adquiridos.",
    "Contratos com tratamento de dados pessoais devem conter base legal, finalidade, papéis das partes, medidas de segurança, retenção, descarte e resposta a incidentes.",
    "Cláusulas de confidencialidade devem definir informação confidencial, exceções, prazo de sigilo, obrigações de proteção e consequências do vazamento.",
    "Contratos de prestação de serviços devem conter níveis de serviço, critérios de aceite, suporte, disponibilidade, responsabilidades por falhas e limites de retrabalho.",
    "Contratos com propriedade intelectual devem definir titularidade, licença de uso, direitos sobre entregáveis, código-fonte, materiais pré-existentes e uso posterior.",
    "Limitações de responsabilidade devem ser avaliadas com atenção para não excluir dolo, fraude, violação de confidencialidade, infração de dados ou obrigações essenciais.",
    "Cláusulas de indenização devem deixar claro quais perdas são indenizáveis, procedimento de defesa, dever de mitigação e limites financeiros aplicáveis.",
    "Contratos de adesão e relações de consumo exigem atenção a cláusulas abusivas, desequilíbrio excessivo, renúncia indevida de direitos e restrição desproporcional de garantias.",
    "A eleição de foro, arbitragem ou mediação deve ser compatível com o tipo de relação, capacidade econômica das partes e urgência de eventuais medidas judiciais.",
    "Cláusulas de compliance devem prever cumprimento de leis anticorrupção, sanções, prevenção à lavagem de dinheiro, auditoria e rescisão por violação grave.",
    "A revisão contratual deve apontar inconsistências internas, como definições usadas antes de serem explicadas, termos diferentes para a mesma obrigação e referências cruzadas incorretas.",
    "Uma melhoria contratual útil é transformar obrigações genéricas em comandos verificáveis, com evidências, prazos, responsáveis e critérios objetivos de cumprimento.",
    "Quando houver assimetria entre as partes, a LLM deve sinalizar cláusulas que concentram riscos em apenas um lado sem justificativa comercial evidente.",
    "O contexto de revisão deve diferenciar sugestão de melhoria, risco jurídico, lacuna operacional, ambiguidade textual e ponto que exige validação por advogado.",
]


def build_contract_context_chunks(
    language: str = "pt",
    max_results_per_topic: int = 3,
    max_chunks_per_topic: int = 12,
    chunk_size: int = 700,
    overlap: int = 80,
    wikipedia_delay_seconds: float = 1.0,
) -> list[str]:
    chunks: list[str] = []

    chunks.extend(prefix_chunks(CONTRACT_REVIEW_SENTENCES))

    for topic in WIKIPEDIA_TOPICS:
        wikipedia_chunks = scrape_wikipedia_for_rag(
            query=topic.query,
            language=language,
            max_results=max_results_per_topic,
            chunk_size=chunk_size,
            overlap=overlap,
            delay_seconds=wikipedia_delay_seconds,
        )

        selected_chunks = filter_relevant_chunks(
            [chunk.text for chunk in wikipedia_chunks],
            max_chunks=max_chunks_per_topic,
        )
        chunks.extend(
            prefix_chunks(
                selected_chunks
            )
        )
        sleep(wikipedia_delay_seconds)

    return dedupe_chunks(chunks)


def build_contract_review_sentence_chunks() -> list[str]:
    return prefix_chunks(CONTRACT_REVIEW_SENTENCES)


def build_wikipedia_topic_chunks(
    topic: WikipediaTopic,
    language: str = "pt",
    max_results_per_topic: int = 3,
    max_chunks_per_topic: int = 12,
    chunk_size: int = 700,
    overlap: int = 80,
    wikipedia_delay_seconds: float = 1.0,
) -> list[str]:
    wikipedia_chunks = scrape_wikipedia_for_rag(
        query=topic.query,
        language=language,
        max_results=max_results_per_topic,
        chunk_size=chunk_size,
        overlap=overlap,
        delay_seconds=wikipedia_delay_seconds,
    )

    selected_chunks = filter_relevant_chunks(
        [chunk.text for chunk in wikipedia_chunks],
        max_chunks=max_chunks_per_topic,
    )

    return dedupe_chunks(
        prefix_chunks(
            selected_chunks
        )
    )


def filter_relevant_chunks(chunks: list[str], max_chunks: int) -> list[str]:
    scored_chunks = []

    for chunk in chunks:
        score = relevance_score(chunk)
        if score <= 0:
            continue
        scored_chunks.append((score, chunk))

    scored_chunks.sort(key=lambda item: item[0], reverse=True)
    return [chunk for _, chunk in scored_chunks[:max_chunks]]


def relevance_score(text: str) -> int:
    lower = text.lower()
    terms = [
        "contrato",
        "contratual",
        "obrigação",
        "obrigações",
        "cláusula",
        "inadimplemento",
        "responsabilidade",
        "indenização",
        "consumidor",
        "dados pessoais",
        "arbitragem",
        "rescisão",
        "multa",
        "direito civil",
        "boa-fé",
    ]
    return sum(lower.count(term) for term in terms)


def prefix_chunks(chunks: list[str]) -> list[str]:
    return [f"{normalize_chunk(chunk)}" for chunk in chunks]


def normalize_chunk(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def dedupe_chunks(chunks: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()

    for chunk in chunks:
        key = normalize_chunk(chunk).lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(chunk)

    return deduped


def ingest_contract_context(
    language: str = "pt",
    max_results_per_topic: int = 3,
    max_chunks_per_topic: int = 12,
    chunk_size: int = 700,
    overlap: int = 80,
    wikipedia_delay_seconds: float = 1.0,
    dry_run: bool = False,
) -> list[str]:
    all_chunks: list[str] = []

    if not dry_run:
        from app.rag.ingestion.ingest import embedAndStore

    review_chunks = build_contract_review_sentence_chunks()
    all_chunks.extend(review_chunks)

    if not dry_run and review_chunks:
        embedAndStore(
            review_chunks,
            title="Diretrizes práticas para revisão de contratos",
            source="contract_review_guidelines",
        )
        print(f"Ingested {len(review_chunks)} guideline chunks.")

    for topic in WIKIPEDIA_TOPICS:
        try:
            topic_chunks = build_wikipedia_topic_chunks(
                topic=topic,
                language=language,
                max_results_per_topic=max_results_per_topic,
                max_chunks_per_topic=max_chunks_per_topic,
                chunk_size=chunk_size,
                overlap=overlap,
                wikipedia_delay_seconds=wikipedia_delay_seconds,
            )
        except Exception as exc:
            print(f"Skipping topic '{topic.label}' after fetch error: {exc}")
            sleep(wikipedia_delay_seconds)
            continue

        all_chunks.extend(topic_chunks)

        if not dry_run and topic_chunks:
            embedAndStore(
                topic_chunks,
                title=f"Contexto Wikipedia: {topic.label.replace('_', ' ')}",
                source=f"wikipedia_{language}_{topic.label}",
            )
            print(f"Ingested {len(topic_chunks)} chunks for topic '{topic.label}'.")

        sleep(wikipedia_delay_seconds)

    return dedupe_chunks(all_chunks)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest contract-review context chunks into the RAG vector database."
    )
    parser.add_argument("--language", default="pt")
    parser.add_argument("--max-results-per-topic", type=int, default=3)
    parser.add_argument("--max-chunks-per-topic", type=int, default=12)
    parser.add_argument("--chunk-size", type=int, default=700)
    parser.add_argument("--overlap", type=int, default=80)
    parser.add_argument("--wikipedia-delay-seconds", type=float, default=1.0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--preview", type=int, default=3)
    args = parser.parse_args()

    chunks = ingest_contract_context(
        language=args.language,
        max_results_per_topic=args.max_results_per_topic,
        max_chunks_per_topic=args.max_chunks_per_topic,
        chunk_size=args.chunk_size,
        overlap=args.overlap,
        wikipedia_delay_seconds=args.wikipedia_delay_seconds,
        dry_run=args.dry_run,
    )

    action = "Prepared" if args.dry_run else "Ingested"
    print(f"{action} {len(chunks)} contract context chunks.")

    for index, chunk in enumerate(chunks[: args.preview], start=1):
        print(f"\n--- chunk {index} ---")
        print(chunk[:1000])


if __name__ == "__main__":
    main()

