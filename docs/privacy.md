## Moonshot: Data Processing and Security
https://www.kimi.com/en/help/kimi-api/api-data-security

Kimi API takes user data security and privacy protection very seriously. Below are answers to common questions.

### Will user data be used for model training?

No. User data submitted via the API, including input content and model outputs, will not be used to train or improve Kimi models. Your data is used only to fulfill the current API request. Once processing is complete, it will not be persistently stored for training purposes.

### How is private-domain data protected?

Kimi API uses multiple safeguards to protect your private-domain data:

  - Encrypted transmission: All API communications are encrypted with HTTPS/TLS.
  - Data isolation: Data from different users is strictly isolated and cannot be viewed by others.
  - Not used for training: API data is not used for model training.
  - Access control: The API Key authentication mechanism ensures that only authorized requests can access your data.
  - Compliance certifications: The platform has obtained relevant security and compliance certifications.

If you have higher security requirements, contact the sales team to learn about enterprise-grade security solutions.

### Content safety review mechanism

Kimi API has a built-in content safety review mechanism:

  - The system automatically detects and filters non-compliant content, such as content involving illegal activity, violence, or pornography.
  - When content safety review is triggered, the API returns the corresponding error message.
  - Content review does not store or disclose your original data.

If you believe it was triggered by mistake, contact customer support with the request_id.

## Gemini

Has a free tier, but free-tier content is used to improve Google's products — likely unacceptable for student work; use paid tier.

## Qwen

Qwen is an open-weight model published by Alibaba — unlike Moonshot/Gemini above, there is no single
API or policy for "Qwen." Privacy depends entirely on which company actually runs the inference
request. Document the specific host actually in use below; do not treat "we use Qwen" as a privacy
statement on its own.

### DeepInfra (candidate host)
https://deepinfra.com/privacy

> We understand that the inputs you provide to our API and the outputs it generates may contain
> your Personal Information. We will not store, sell, or train using this data unless we have your
> explicit consent.

> Your data may be transferred, stored, and processed outside of your jurisdiction, specifically in
> the United States.

DeepInfra, Inc. is a named Delaware company with a published policy, the same shape as the Moonshot
entry above. Cross-border transfer is to the US, not China, regardless of Qwen's origin — model
nationality and data-processing location are independent questions.

### Alibaba Cloud (Model Studio / DashScope) — not yet verified

If Qwen is called through Alibaba's own first-party API instead of a re-host, it is the closest
equivalent to the Moonshot/Gemini entries (one accountable vendor). We have not yet been able to
confirm Alibaba Cloud's specific data-training/retention policy for this API. Apply the same
due-diligence pass done for Moonshot before relying on it for student submissions, and replace this
note with the verified policy once found.

### Hosts to avoid: decentralized/marketplace compute

Chutes (and similar "decentralized compute" marketplaces, e.g. built on Bittensor) explicitly route
inference across distributed, third-party participants rather than one accountable datacenter
operator. There is no single counterparty to hold to a data policy. Do not use these for student
data regardless of price.

### Self-hosting

Running Qwen on infrastructure under our control (e.g. a rented GPU pod) means no inference vendor
ever receives student images or text at all — the strongest privacy posture of any option considered
here, at the cost of operating the model ourselves. The GPU cloud provider in that case is
infrastructure only, not a data processor of prompt content.