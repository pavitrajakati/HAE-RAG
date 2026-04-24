# ================================================================
# backend/response_builder.py  (v2)
# ================================================================

import json


class ResponseBuilder:

    def build(self, query, generation_result, verification_result):
        sa      = verification_result["sentences"]
        summary = verification_result["verification_summary"] \
                  if "verification_summary" in verification_result \
                  else verification_result

        answer_type = verification_result.get("answer_type", "prose")

        return {
            "query":   query,
            "answer":  generation_result["answer"],
            "answer_type": answer_type,

            "sentence_analysis": [
                {
                    "sentence":   s["sentence"],
                    "label":      s["label"],
                    "confidence": s["confidence"],
                    "evidence":   s["evidence"],
                    "source":     s.get("source", {}),
                }
                for s in sa
            ],

            "verification_summary": {
                "verdict":            summary.get("verdict"),
                "overall_score":      summary.get("overall_score"),
                "verified_count":     summary.get("verified_count"),
                "partial_count":      summary.get("partial_count"),
                "hallucinated_count": summary.get("hallucinated_count"),
                "total_sentences":    summary.get("total_sentences"),
            },

            "retrieved_chunks": [
                {
                    "text":   c["text"][:200],
                    "source": c["metadata"].get("source"),
                    "type":   c["metadata"].get("chunk_type"),
                    "score":  c["score"],
                }
                for c in generation_result["retrieved_chunks"]
            ],
        }

    def display(self, response):
        EMOJI = {"VERIFIED": "✅", "PARTIAL": "⚠️ ", "HALLUCINATED": "❌"}
        VERDICT_EMOJI = {"TRUSTWORTHY": "✅", "MIXED": "⚠️ ", "UNRELIABLE": "❌"}

        print("\n" + "="*65)
        print(f"QUESTION: {response['query']}")
        print("="*65)
        print(f"\n📝 ANSWER ({response.get('answer_type','prose').upper()}):\n")
        print(response["answer"])

        print("\n" + "-"*65)
        print("🔍 VERIFICATION:\n")

        sa = response["sentence_analysis"]
        if response.get("answer_type") == "list":
            # List answer — show as single unit
            s     = sa[0]
            emoji = EMOJI.get(s["label"], "?")
            print(f"{emoji} WHOLE ANSWER: {s['label']} ({s['confidence']:.0%})")
            if s["evidence"]:
                print(f"   Evidence: {s['evidence'][:150]}...")
        else:
            for i, s in enumerate(sa, 1):
                emoji = EMOJI.get(s["label"], "?")
                print(f"{emoji} [{i}] {s['label']} ({s['confidence']:.0%})")
                print(f"   {s['sentence']}")
                if s["evidence"]:
                    print(f"   Evidence: {s['evidence'][:120]}...")
                print()

        summary = response["verification_summary"]
        verdict = summary["verdict"]
        emoji   = VERDICT_EMOJI.get(verdict, "?")
        print(f"\n📊 VERDICT: {emoji} {verdict} | Score: {summary['overall_score']:.0%}")
        print("="*65 + "\n")

    def to_json(self, response):
        return json.dumps(response, indent=2, ensure_ascii=False)