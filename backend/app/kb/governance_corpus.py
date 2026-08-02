"""
governance_corpus.py
Framework-tagged obligations for the governance knowledge base.

Each entry: {id, framework, ref, title, text}
  framework -> stored in the Qdrant payload so /kb/search can filter on it
               (matches the values the Policy Retrieval node sends)

These are concise, accurate obligation summaries suitable for grounding the
compliance agent. They are NOT the full legal text. Before you lean on any
specific article number in an interview, cross-check it against the official
source (EUR-Lex for the AI Act/GDPR, ISO for 42001, NIST for the AI RMF).
You can expand any entry with fuller text later; the ingest keeps working.
"""

CORPUS = [

    # ------------------------------------------------ EU AI ACT
    {
        "id": "eu-ai-act-art5",
        "framework": "EU_AI_ACT",
        "ref": "Article 5",
        "title": "Prohibited AI practices (unacceptable risk)",
        "text": ("The EU AI Act prohibits AI systems that deploy subliminal or manipulative "
                 "techniques causing significant harm, exploit vulnerabilities of specific groups, "
                 "perform social scoring by public authorities, carry out untargeted scraping of "
                 "facial images, infer emotions in workplaces or education, use biometric "
                 "categorisation to deduce sensitive attributes, or conduct real-time remote "
                 "biometric identification in public spaces (save narrow law-enforcement "
                 "exceptions). Such uses are classed as unacceptable risk and are banned outright."),
    },
    {
        "id": "eu-ai-act-art6-annex3",
        "framework": "EU_AI_ACT",
        "ref": "Article 6 & Annex III",
        "title": "High-risk classification",
        "text": ("AI systems are high-risk when used in biometrics, critical infrastructure, "
                 "education and vocational training, employment and worker management, access to "
                 "essential private and public services (including creditworthiness and credit "
                 "scoring), law enforcement, migration and border control, and the administration "
                 "of justice. High-risk systems trigger the full obligations in Articles 9 to 15."),
    },
    {
        "id": "eu-ai-act-art9",
        "framework": "EU_AI_ACT",
        "ref": "Article 9",
        "title": "Risk management system",
        "text": ("Providers of high-risk AI must establish, implement and maintain a continuous, "
                 "iterative risk management system across the system's lifecycle, identifying and "
                 "evaluating foreseeable risks to health, safety and fundamental rights and adopting "
                 "targeted mitigation measures."),
    },
    {
        "id": "eu-ai-act-art10",
        "framework": "EU_AI_ACT",
        "ref": "Article 10",
        "title": "Data and data governance",
        "text": ("Training, validation and testing data for high-risk AI must be relevant, "
                 "sufficiently representative, and to the extent possible free of errors and "
                 "complete. Providers must examine datasets for possible biases likely to affect "
                 "health, safety or fundamental rights, and apply appropriate governance measures."),
    },
    {
        "id": "eu-ai-act-art12",
        "framework": "EU_AI_ACT",
        "ref": "Article 12",
        "title": "Record-keeping and logging",
        "text": ("High-risk AI systems must technically allow for the automatic recording of events "
                 "(logs) over the system's lifetime, ensuring a level of traceability appropriate to "
                 "the intended purpose so that functioning can be monitored and post-market "
                 "incidents investigated."),
    },
    {
        "id": "eu-ai-act-art13",
        "framework": "EU_AI_ACT",
        "ref": "Article 13",
        "title": "Transparency and information to deployers",
        "text": ("High-risk AI must be sufficiently transparent for deployers to interpret output and "
                 "use it appropriately, accompanied by clear instructions covering capabilities, "
                 "limitations, expected accuracy, and known risks."),
    },
    {
        "id": "eu-ai-act-art14",
        "framework": "EU_AI_ACT",
        "ref": "Article 14",
        "title": "Human oversight",
        "text": ("High-risk AI systems must be designed so they can be effectively overseen by "
                 "natural persons during use, enabling a human to understand the system, monitor its "
                 "operation, intervene or interrupt it, and decide not to use its output. Automated "
                 "high-impact actions should not proceed without meaningful human oversight."),
    },
    {
        "id": "eu-ai-act-art15",
        "framework": "EU_AI_ACT",
        "ref": "Article 15",
        "title": "Accuracy, robustness and cybersecurity",
        "text": ("High-risk AI must achieve appropriate levels of accuracy, robustness and "
                 "cybersecurity, perform consistently across its lifecycle, and be resilient against "
                 "errors, faults, inconsistencies and attempts to manipulate inputs or exploit "
                 "vulnerabilities."),
    },
    {
        "id": "eu-ai-act-art50",
        "framework": "EU_AI_ACT",
        "ref": "Article 50",
        "title": "Transparency obligations for certain AI systems",
        "text": ("Providers must ensure people are informed when they are interacting with an AI "
                 "system unless it is obvious. Emotion-recognition and biometric-categorisation use "
                 "must be disclosed to the people exposed to it, and AI-generated or manipulated "
                 "content (including deepfakes) must be marked as artificially generated."),
    },

    # ------------------------------------------------ GDPR
    {
        "id": "gdpr-art5",
        "framework": "GDPR",
        "ref": "Article 5",
        "title": "Principles of processing",
        "text": ("Personal data must be processed lawfully, fairly and transparently; collected for "
                 "specified, explicit and legitimate purposes; limited to what is necessary "
                 "(data minimisation); accurate; kept no longer than needed (storage limitation); "
                 "and processed securely. The controller is accountable for demonstrating "
                 "compliance."),
    },
    {
        "id": "gdpr-art6",
        "framework": "GDPR",
        "ref": "Article 6",
        "title": "Lawfulness of processing",
        "text": ("Processing is lawful only if at least one basis applies: consent, contract, legal "
                 "obligation, vital interests, public task, or legitimate interests balanced against "
                 "the data subject's rights."),
    },
    {
        "id": "gdpr-art9",
        "framework": "GDPR",
        "ref": "Article 9",
        "title": "Special categories of personal data",
        "text": ("Processing of sensitive data (racial or ethnic origin, political opinions, "
                 "religious beliefs, health, biometric or genetic data, sexual orientation) is "
                 "prohibited unless a specific exception such as explicit consent or substantial "
                 "public interest applies."),
    },
    {
        "id": "gdpr-art22",
        "framework": "GDPR",
        "ref": "Article 22",
        "title": "Automated individual decision-making",
        "text": ("A data subject has the right not to be subject to a decision based solely on "
                 "automated processing, including profiling, that produces legal or similarly "
                 "significant effects, unless it is necessary for a contract, authorised by law, or "
                 "based on explicit consent, with safeguards including the right to human "
                 "intervention."),
    },
    {
        "id": "gdpr-art25",
        "framework": "GDPR",
        "ref": "Article 25",
        "title": "Data protection by design and by default",
        "text": ("Controllers must implement appropriate technical and organisational measures, such "
                 "as pseudonymisation and data minimisation, both at the time of determining the "
                 "means of processing and during processing itself, ensuring only necessary data is "
                 "processed by default."),
    },
    {
        "id": "gdpr-art32",
        "framework": "GDPR",
        "ref": "Article 32",
        "title": "Security of processing",
        "text": ("Controllers and processors must implement security appropriate to the risk, "
                 "including encryption and pseudonymisation where suitable, and the ability to ensure "
                 "ongoing confidentiality, integrity, availability and resilience of processing "
                 "systems."),
    },
    {
        "id": "gdpr-art35",
        "framework": "GDPR",
        "ref": "Article 35",
        "title": "Data protection impact assessment",
        "text": ("Where processing is likely to result in a high risk to individuals' rights, "
                 "particularly using new technologies or large-scale profiling, the controller must "
                 "carry out a data protection impact assessment before processing."),
    },

    # ------------------------------------------------ ISO/IEC 42001:2023
    {
        "id": "iso42001-cl5",
        "framework": "ISO_42001",
        "ref": "Clause 5",
        "title": "Leadership and AI policy",
        "text": ("Top management must demonstrate leadership over the AI management system, establish "
                 "an AI policy aligned with organisational objectives and responsible-AI principles, "
                 "and assign clear roles and responsibilities for AI governance."),
    },
    {
        "id": "iso42001-cl6",
        "framework": "ISO_42001",
        "ref": "Clause 6",
        "title": "Planning and AI risk assessment",
        "text": ("The organisation must plan the AI management system by assessing AI-related risks "
                 "and opportunities, defining a risk assessment and treatment process, and setting "
                 "measurable AI objectives with plans to achieve them."),
    },
    {
        "id": "iso42001-cl8",
        "framework": "ISO_42001",
        "ref": "Clause 8 / Annex A.5",
        "title": "Operation and AI system impact assessment",
        "text": ("The organisation must plan and control AI operations and conduct AI system impact "
                 "assessments that consider consequences for individuals and society throughout the "
                 "AI system life cycle."),
    },
    {
        "id": "iso42001-cl9",
        "framework": "ISO_42001",
        "ref": "Clause 9",
        "title": "Performance evaluation",
        "text": ("The organisation must monitor, measure, analyse and evaluate the AI management "
                 "system, conduct internal audits, and hold management reviews to confirm the system "
                 "remains suitable, adequate and effective."),
    },
    {
        "id": "iso42001-annexA7",
        "framework": "ISO_42001",
        "ref": "Annex A.7",
        "title": "Data for AI systems",
        "text": ("Controls require managing data used to develop and operate AI systems, covering "
                 "data quality, provenance, and the acquisition and preparation processes, so that "
                 "data is fit for its intended purpose."),
    },

    # ------------------------------------------------ NIST AI RMF 1.0
    {
        "id": "nist-govern",
        "framework": "NIST_AI_RMF",
        "ref": "GOVERN",
        "title": "Govern function",
        "text": ("A culture of AI risk management is cultivated and present: policies, processes and "
                 "accountability structures are in place, roles and responsibilities are clear, risk "
                 "tolerances are defined, and workforce diversity and third-party risks are "
                 "addressed across the AI lifecycle."),
    },
    {
        "id": "nist-map",
        "framework": "NIST_AI_RMF",
        "ref": "MAP",
        "title": "Map function",
        "text": ("Context is established and risks are framed: the intended purpose, deployment "
                 "setting, capabilities, and potential positive and negative impacts of the AI system "
                 "are identified and categorised so that downstream measurement is meaningful."),
    },
    {
        "id": "nist-measure",
        "framework": "NIST_AI_RMF",
        "ref": "MEASURE",
        "title": "Measure function",
        "text": ("Identified risks are analysed, assessed, benchmarked and monitored using "
                 "quantitative and qualitative methods against the trustworthiness characteristics: "
                 "valid and reliable, safe, secure and resilient, accountable and transparent, "
                 "explainable and interpretable, privacy-enhanced, and fair with harmful bias "
                 "managed."),
    },
    {
        "id": "nist-manage",
        "framework": "NIST_AI_RMF",
        "ref": "MANAGE",
        "title": "Manage function",
        "text": ("Risks are prioritised and acted upon based on projected impact: resources are "
                 "allocated to treat, monitor and respond to risks, incident response and recovery "
                 "plans are maintained, and residual and third-party risks are tracked over time."),
    },
]


def by_framework(name):
    return [c for c in CORPUS if c["framework"] == name]


if __name__ == "__main__":
    from collections import Counter
    counts = Counter(c["framework"] for c in CORPUS)
    print(f"{len(CORPUS)} chunks across {len(counts)} frameworks:")
    for k, v in counts.items():
        print(f"  {k}: {v}")
