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
