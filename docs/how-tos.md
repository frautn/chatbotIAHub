## Create an activity in a modern Moodle site

More information in docker/readme.txt

### Add new LTI 1.1 External tool.

Consider this value in docker/.env: LTI11_PUBLIC_URL=https://lti11.example.com

These are the values for the Moodle External Tool:

Give it a name  
Tool URL = https://lti11.example.com/lti11/launch  
Tool description = Can be empty  
LTI version = LTI 1.0/1.1   
Consumer Key = LTI11_CONSUMER_KEY in docker/.env  
Shared Secret = LTI11_CONSUMER_SECRET in docker/.env  
Custom parameters = leave it empty  
Default launch container = New Window  
Do not select: Supports Deep Linking (Content-Item Message)  
Content selection URL = empty  
IMS LTI Assignment and Grade Services = Use this service for grade sync and column management  
IMS LTI Names and Role Provisioning = USe this service to retrieve member's information as per privacy settings  

#### Add activity in the course

Add content -> Find the name given in the previous step  
Activity name = A name  
Activity description = A description  
Custom parameters : model=calorimetria-ej-003 (use the name of the model in the Opwn-WebUI workspace)  
&#x21B3; (Currently, the model needs to be added to the list in docker/.env (LTI11_GATEWAY_MODELS))