35_Conversational_Intelligence.md

Document ID: RDM-035
Document Name: Conversational Intelligence
Domain Pack: Restaurant Intelligence Platform
Product: Enterprise Conversational Intelligence Platform (ECIP)
Version: 1.0.0
Status: ACTIVE
Certification Status: APPROVED

1. PURPOSE

This document defines the Conversational Intelligence Model for the Restaurant Intelligence Platform.

Its purpose is to transform every authorized conversation between the restaurant and Customers, Employees, Suppliers, Partners or other actors into a structured, contextual, actionable and reusable source of enterprise intelligence.

Conversational Intelligence is not:

A chatbot.
An IVR.
A voice assistant.
A speech-to-text system.
A messaging interface.
A call-center script.
A collection of LLM prompts.

It is the intelligence layer that enables ECIP to understand conversations independently of the communication channel and connect them with the real operational and commercial state of the restaurant.

The platform shall understand:

WHO IS COMMUNICATING?


THROUGH WHICH CHANNEL?


WHAT ARE THEY TRYING TO ACCOMPLISH?


WHAT HAVE THEY ALREADY SAID?


WHAT DOES THE RESTAURANT ALREADY KNOW?


WHAT BUSINESS ENTITIES ARE BEING DISCUSSED?


WHAT CONTEXT IS RELEVANT?


WHAT IS FACT?


WHAT IS AN INFERENCE?


WHAT IS STILL UNKNOWN?


WHAT DECISION MUST BE MADE?


WHAT ACTION SHOULD OCCUR?


CAN ECIP EXECUTE THAT ACTION?


DOES A HUMAN NEED TO INTERVENE?


WHAT SHOULD BE REMEMBERED?


WHAT BUSINESS KNOWLEDGE CAN BE LEARNED?

The objective is not merely to understand language.

The objective is to transform conversation into business understanding, decisions, actions and institutional knowledge.

2. STRATEGIC ROLE

Conversational Intelligence is one of the central capabilities of ECIP.

Conceptually:

COMMUNICATION CHANNELS
        │
        ▼
CONVERSATIONAL INTELLIGENCE
        │
        ▼
ENTERPRISE INTELLIGENCE
        │
        ├── Customer Intelligence
        ├── Sales Intelligence
        ├── Operational Intelligence
        ├── Menu Intelligence
        ├── Inventory Intelligence
        ├── Reservation Intelligence
        ├── Financial Intelligence
        └── Future Intelligence Domains
        │
        ▼
DECISION
        │
        ▼
ACTION
        │
        ▼
OUTCOME
        │
        ▼
ENTERPRISE LEARNING

Conversational Intelligence therefore acts as a bridge between:

HUMAN LANGUAGE


and


ENTERPRISE STATE
3. CORE PRINCIPLE

ECIP shall be:

Channel-independent, context-aware, business-aware and action-oriented.

A conversation shall not be modeled according to whether it originated from Telephone, WhatsApp or Web Chat.

Those are communication transports.

The underlying intelligence model shall remain stable.

4. CHANNEL INDEPENDENCE

Initial and future Channels may include:

TELEPHONE


WHATSAPP


SMS


WEB_CHAT


MOBILE_APP


FACEBOOK_MESSENGER


INSTAGRAM


TELEGRAM


GOOGLE_BUSINESS_MESSAGES


EMAIL


KIOSK


SMART_DISPLAY


VOICE_ASSISTANT


INTERNAL_EMPLOYEE_CHAT


INTELLIGENT_AGENT


FUTURE_CHANNEL

Adding a new Channel shall not require redesigning the core Conversational Intelligence Model.

5. CHANNEL ADAPTER PRINCIPLE

Channels shall connect through adapters.

Conceptually:

Telephone ────────────┐
WhatsApp ─────────────┤
SMS ──────────────────┤
Web Chat ─────────────┤
Mobile App ───────────┤
Instagram ────────────┤
Kiosk ────────────────┤
Future Channel ───────┘
          │
          ▼
CHANNEL ADAPTER LAYER
          │
          ▼
CANONICAL CONVERSATION MODEL
          │
          ▼
CONVERSATIONAL INTELLIGENCE

Channel-specific behavior shall remain outside the canonical business model wherever possible.

6. RELATIONSHIP WITH THE CANONICAL MODEL

This document extends and consumes canonical concepts including:

Actor
Identity
Channel
Interaction
Conversation
Message
Utterance
Intent
Entity
Context
Context Snapshot
Observation
Signal
Commitment
Recommendation
Decision
Action
Outcome
Evidence Record
External Entity Reference

Restaurant-specific conversational semantics remain within the Restaurant Domain Pack.

7. RELATIONSHIP WITH CUSTOMER INTELLIGENCE

33_Customer_Intelligence.md answers:

WHO IS THIS CUSTOMER?


WHAT DO WE KNOW ABOUT THE RELATIONSHIP?

Conversational Intelligence answers:

WHAT IS HAPPENING IN THIS CONVERSATION?


WHAT DOES THE CUSTOMER MEAN?


WHAT DO THEY NEED?


WHAT SHOULD HAPPEN NEXT?

The two domains cooperate but remain distinct.

8. RELATIONSHIP WITH SALES INTELLIGENCE

32_Sales_Intelligence.md determines:

WHAT COMMERCIAL OPPORTUNITY EXISTS?

Conversational Intelligence determines:

IS A COMMERCIAL RECOMMENDATION APPROPRIATE
IN THIS CONVERSATION RIGHT NOW?
9. RELATIONSHIP WITH OPERATIONAL INTELLIGENCE

34_Operational_Intelligence.md determines:

WHAT CAN THE RESTAURANT ACTUALLY DELIVER?

Conversational Intelligence uses this information before making commitments.

Example:

Customer:
"Can you have four pizzas ready in 20 minutes?"


Conversational Intelligence
        +
Operational Intelligence
        ↓
Reliable response
10. CONVERSATION

A Conversation represents a logical communication process involving one or more actors around one or more goals.

A Conversation may span:

Multiple Messages.
Multiple Calls.
Multiple Sessions.
Multiple Channels.
Multiple Employees.
Multiple days.

Therefore:

CONVERSATION ≠ SESSION

and:

CONVERSATION ≠ PHONE CALL
11. CONVERSATION ATTRIBUTES

Typical attributes include:

Conversation ID.
Tenant.
Restaurant Organization.
Branch.
Participants.
Customer reference.
Channel references.
Started time.
Last activity time.
Current state.
Current Intent.
Conversation Goal.
Context.
Related business entities.
Assigned Employee/Agent.
Escalation state.
Resolution state.
12. CONVERSATION STATE

Suggested lifecycle:

CREATED
→ ACTIVE
→ WAITING
→ RESUMED
→ RESOLVED
→ CLOSED

Additional states may include:

ESCALATED


ABANDONED


EXPIRED
13. CONVERSATION SESSION

A ConversationSession represents a continuous period of interaction through a Channel.

Example:

Conversation:
Birthday Event Planning


Session 1:
WhatsApp — Monday


Session 2:
Telephone — Wednesday


Session 3:
Web Chat — Friday

All may belong to one logical Conversation.

14. INTERACTION

An Interaction represents a meaningful communication occurrence.

Examples:

Incoming call.
Outgoing call.
Incoming Message.
Employee response.
AI response.
Customer button selection.
Kiosk interaction.
Agent-to-agent communication.
15. MESSAGE

A Message represents a communication unit transported through a Channel.

Potential content types:

TEXT


AUDIO


IMAGE


VIDEO


DOCUMENT


LOCATION


STRUCTURED_PAYLOAD


INTERACTIVE_RESPONSE


SYSTEM_EVENT
16. UTTERANCE

An Utterance represents a semantic unit expressed by an actor.

One Message may contain multiple Utterances.

Example:

"I want a table for four tonight,
and do you have anything for birthdays?"

Possible Utterances:

Reservation Request


Birthday Service Inquiry
17. SPEAKER / ACTOR

Every conversational contribution should preserve its actor when known.

Possible actors include:

CUSTOMER


EMPLOYEE


MANAGER


SUPPLIER


AI


INTELLIGENT_AGENT


EXTERNAL_SYSTEM


UNKNOWN
18. ACTOR IDENTITY

Actor identity shall remain separate from Channel identity.

Example:

Telephone number:
+52...


WhatsApp identity:
+52...


Mobile App account:
CUST-0184


        ↓


Canonical Actor:
CUSTOMER-0184
19. IDENTITY CONFIDENCE

Conversational Intelligence shall consume identity confidence from the appropriate identity/customer domain.

It shall not expose sensitive information when identity resolution is insufficient.

20. CONVERSATION PARTICIPANT

A Conversation may include multiple participants.

Example:

Customer
Customer's spouse
AI Agent
Restaurant Employee
Manager

The platform shall not assume every statement belongs to the same person.

21. CONVERSATIONAL INTENT

A ConversationalIntent represents what an actor is trying to accomplish.

Examples:

ASK_INFORMATION


EXPLORE_MENU


REQUEST_RECOMMENDATION


PLACE_ORDER


MODIFY_ORDER


CANCEL_ORDER


MAKE_RESERVATION


MODIFY_RESERVATION


CANCEL_RESERVATION


CHECK_STATUS


PLAN_EVENT


MAKE_COMPLAINT


REQUEST_REFUND


GIVE_COMPLIMENT


ASK_FOR_EMPLOYEE


REQUEST_SUPPORT


ASK_BILLING_QUESTION
22. MULTI-INTENT CONVERSATION

A Conversation may contain multiple simultaneous or sequential Intents.

Example:

"I want to reserve for six,
and one person is allergic to peanuts,
and we'd like a birthday cake."

Potential Intents:

MAKE_RESERVATION


DECLARE_DIETARY_OR_SAFETY_CONSTRAINT


REQUEST_EVENT_SERVICE
23. INTENT HIERARCHY

Intent may be represented hierarchically.

Example:

ORDER
 ├── CREATE
 ├── MODIFY
 ├── CANCEL
 └── CHECK_STATUS

This allows extensibility without creating an uncontrolled flat Intent catalog.

24. INTENT CONFIDENCE

Detected Intents shall preserve confidence.

Suggested categories:

CONFIRMED


HIGH


MEDIUM


LOW


UNKNOWN
25. EXPLICIT VS INFERRED INTENT

The platform shall distinguish:

EXPLICIT:
"I want to reserve a table."


INFERRED:
"Do you have room for six tonight?"

Both may indicate Reservation Intent, but evidence differs.

26. INTENT CHANGE

Intent may change during the Conversation.

Example:

Initial:
Ask Menu Information


Then:
Request Recommendation


Then:
Place Order

The Conversation shall preserve this evolution.

27. CUSTOMER GOAL

Intent describes the immediate objective.

Goal may describe the broader desired outcome.

Example:

Intent:
MAKE_RESERVATION


Goal:
ORGANIZE_BIRTHDAY_DINNER

Understanding Goal may improve multi-step assistance.

28. CONVERSATIONAL ENTITY

A ConversationalEntity represents a business-relevant entity mentioned or referenced in Conversation.

Examples:

Product.
Ingredient.
Customer.
Branch.
Employee.
Reservation.
Order.
Table.
Event.
Promotion.
Payment.
Invoice.
Date.
Time.
Quantity.
29. ENTITY RESOLUTION

Mention:

"the downtown restaurant"

may resolve to:

RestaurantLocation:
LOCATION-003

Mention:

"the chicken burger"

may resolve to:

Product:
PRODUCT-019

Resolution confidence shall be preserved.

30. AMBIGUITY

Example:

"I want the special."

If multiple Products match:

AMBIGUOUS ENTITY

ECIP shall clarify rather than silently guess when the distinction matters.

31. CONVERSATIONAL REFERENCE

Conversation frequently contains references such as:

"the same as last time"


"that one"


"my usual"


"the reservation I made yesterday"


"the order we were discussing"

Conversational Intelligence shall resolve these against relevant context.

32. COREFERENCE

Coreference resolution connects references to previously mentioned entities.

Example:

"I want the salmon.


Can you make it without butter?"

it refers to the selected salmon Product or preparation.

33. TEMPORAL REFERENCE

Conversational language may include:

today


tomorrow


tonight


next Friday


in two hours


after work

Temporal interpretation shall consider:

Branch timezone.
Current time.
Conversation context.

Ambiguous dates shall be clarified when materially relevant.

34. QUANTITY UNDERSTANDING

The platform shall correctly distinguish:

4 people


4 tables


4 pizzas


4 orders


4 deliveries

Quantity requires entity context.

35. CONVERSATIONAL CONTEXT

ConversationalContext represents the active knowledge required to interpret the current interaction.

Potential components:

Actor Identity


Current Intent


Current Goal


Conversation History


Resolved Entities


Pending Questions


Current Order


Current Reservation


Relevant Customer Preferences


Relevant Customer History


Current Operational Context


Relevant Policies


Active Commitments
36. CONTEXT LAYERS

Conversational context may be organized into:

TURN CONTEXT


SESSION CONTEXT


CONVERSATION CONTEXT


CUSTOMER CONTEXT


RESTAURANT CONTEXT


OPERATIONAL CONTEXT


ENTERPRISE CONTEXT
37. CONTEXT MINIMIZATION

ECIP shall retrieve only the information required for the current reasoning task.

The platform shall not load the entire restaurant database or entire Customer history into every interaction.

This improves:

Privacy.
Accuracy.
Latency.
Cost.
Explainability.
Security.
38. CONTEXT RELEVANCE

Context shall be selected according to:

WHO?


WHAT INTENT?


WHICH BUSINESS ENTITY?


WHICH BRANCH?


WHICH TIME?


WHICH OPERATION?


WHICH AUTHORIZATION?
39. CONTEXT FRESHNESS

Operational context may change during a Conversation.

Example:

19:00
Product available.


19:05
Last unit sold.


19:07
Customer confirms Order.

ECIP must validate relevant mutable state before making the final commitment.

40. CONTEXT SNAPSHOT

A ConversationContextSnapshot may preserve the information used for a material conversational decision.

This supports auditability.

41. BUSINESS CONTEXT RETRIEVAL

Conversational Intelligence may retrieve information from:

Customer Profile.
Customer Preferences.
Customer History.
Menu.
Product Catalog.
Recipes.
Pricing.
Promotions.
Orders.
Reservations.
Kitchen.
Inventory.
Delivery.
Payments.
Maintenance.
Operational Incidents.
Intelligence domains.

Retrieval shall respect ownership and authorization.

42. READ VS WRITE

Reading business information and changing business state are fundamentally different operations.

Example:

READ:
"Do you have tables available?"


WRITE:
"Reserve one for me."

Writes require explicit domain commands and authorization.

43. CONVERSATIONAL COMMAND

A ConversationalCommand represents a requested business mutation derived from Conversation.

Examples:

CreateOrder


AddOrderItem


CancelOrder


CreateReservation


ModifyReservation


RequestRefund


CreateComplaint


CreateMaintenanceRequest

Conversational Intelligence interprets the request.

The owning domain executes the mutation.

44. OWNERSHIP PRESERVATION

Conversational Intelligence shall never become the owner of business entities merely because the request originated in Conversation.

Example:

Conversation:
"Cancel my reservation."


Conversational Intelligence:
Understands request.


Reservation Domain:
Authorizes and performs cancellation.
45. ACTION

A ConversationalAction represents an action proposed or executed because of conversational reasoning.

Possible categories:

RESPOND


ASK_CLARIFICATION


RETRIEVE_CONTEXT


EXECUTE_DOMAIN_COMMAND


RECOMMEND


NOTIFY


FOLLOW_UP


ESCALATE


WAIT


END_CONVERSATION
46. RESPONSE

A response is not necessarily plain text.

It may be:

Spoken audio.
Text.
Interactive Menu.
Product card.
Reservation options.
Payment link.
Image.
Structured data.
Human transfer.

The semantic response shall remain channel-independent before rendering.

47. SEMANTIC RESPONSE

ECIP should first determine:

WHAT SHOULD BE COMMUNICATED?

and only afterward:

HOW SHOULD THIS CHANNEL PRESENT IT?

Conceptually:

BUSINESS RESPONSE
        ↓
SEMANTIC RESPONSE
        ↓
CHANNEL RENDERING
48. RESPONSE GROUNDING

Material factual responses shall be grounded in authoritative data.

Example:

Customer:
"Is the salmon available?"


Required evidence:
Current Product availability
+
Relevant Inventory / Operational restrictions

The AI shall not answer from general language-model knowledge.

49. RESPONSE CONFIDENCE

If authoritative information is unavailable or stale, ECIP shall communicate uncertainty or obtain confirmation.

50. CONVERSATIONAL TRUTH

The platform shall distinguish:

KNOWN BUSINESS FACT


CUSTOMER STATEMENT


EMPLOYEE STATEMENT


SYSTEM OBSERVATION


AI INFERENCE


PREDICTION

These shall not be treated as equivalent evidence.

51. CUSTOMER STATEMENT

A Customer statement may be authoritative about:

Their preference.
Their requested action.
Their experience.
Their intention.

It may not be authoritative about:

Inventory.
Restaurant policy.
Payment completion.
Equipment state.
52. CLARIFICATION

ECIP shall ask clarification when ambiguity materially affects:

Safety.
Price.
Product.
Quantity.
Date/time.
Location.
Customer identity.
Payment.
Reservation.
Business commitment.
53. MINIMUM CLARIFICATION PRINCIPLE

The platform should ask the minimum number of questions necessary to safely complete the Goal.

It should not reproduce rigid IVR-style interrogation.

54. INFORMATION ALREADY KNOWN

ECIP shall not ask for information it already reliably knows and is authorized to use.

Example:

Known:
Customer
Branch
Reservation
Party size


Do not ask again unnecessarily.
55. CONVERSATIONAL MEMORY

Conversation memory may include:

Current Goal.
Previous Intents.
Resolved entities.
Answers already provided.
Pending decisions.
Active commitments.
Unresolved questions.
56. TEMPORARY MEMORY

Most conversational details may be temporary.

Example:

"I'm driving right now."

This may matter during the current Session but need not become long-term Customer memory.

57. LONG-TERM MEMORY CANDIDATE

Conversation may produce information potentially useful later.

Examples:

"I always prefer a quiet table."


"My company holds this dinner every December."

Conversational Intelligence may generate a memory candidate.

The appropriate Customer or business domain determines whether it becomes authoritative long-term knowledge.

58. MEMORY PROMOTION

Conceptually:

CONVERSATIONAL STATEMENT
        ↓
MEMORY CANDIDATE
        ↓
VALIDATION / POLICY
        ↓
AUTHORITATIVE DOMAIN KNOWLEDGE

Conversational Intelligence shall not indiscriminately store every statement as permanent truth.

59. UNFINISHED CONVERSATION

A Conversation may remain unresolved because it is:

WAITING_FOR_CUSTOMER


WAITING_FOR_EMPLOYEE


WAITING_FOR_RESTAURANT


WAITING_FOR_EXTERNAL_SYSTEM


WAITING_FOR_PAYMENT


WAITING_FOR_APPROVAL
60. CONVERSATION RESUMPTION

ECIP should support:

START
→ PAUSE
→ RESUME

without forcing the Customer to restart the entire process.

61. CROSS-CHANNEL RESUMPTION

Example:

Monday:
Customer starts Event inquiry on WhatsApp.


Tuesday:
Customer calls.


ECIP:
Recognizes relevant open Conversation.


Conversation continues.

Channel change shall not automatically create a new business context.

62. CONVERSATION LINKING

Separate Sessions may be linked based on:

Confirmed identity.
Explicit reference.
Shared business entity.
Open Commitment.
Temporal relevance.

Weak similarity alone shall not automatically merge Conversations.

63. CONVERSATION SPLIT

One Conversation may need to be separated if independent Goals emerge.

Example:

Complaint about yesterday's Delivery


+


New corporate Event inquiry

Both may occur in one Call but require distinct business workflows.

64. CONVERSATIONAL STATE MACHINE

A Conversation should maintain explicit state.

Example:

IDENTIFY
    ↓
UNDERSTAND
    ↓
CLARIFY
    ↓
RETRIEVE
    ↓
DECIDE
    ↓
ACT
    ↓
CONFIRM
    ↓
RESOLVE

Not every Conversation requires every stage.

65. CONVERSATIONAL PLAN

A ConversationPlan represents the sequence of steps required to accomplish a Goal.

Example:

Goal:
Reserve birthday dinner


Plan:


1. Determine Branch
2. Determine date/time
3. Determine party size
4. Check availability
5. Understand birthday requirement
6. Offer relevant options
7. Confirm price/policies
8. Create Reservation
9. Confirm Customer Commitment
66. DYNAMIC PLANNING

Conversation Plans shall not be rigid scripts.

They may change when new information appears.

Example:

Reservation flow
        ↓
Customer mentions 50 guests
        ↓
Transition to Banquet/Event workflow
67. CONVERSATIONAL DECISION

A ConversationalDecision represents a decision made during reasoning.

Examples:

Ask clarification.
Retrieve Customer history.
Suppress upsell.
Escalate.
Execute Reservation command.
Offer alternative Product.
68. DECISION EVIDENCE

Material decisions should preserve:

Intent.
Context.
Relevant facts.
Constraints.
Policy.
Confidence.
Recommended action.
69. NEXT-BEST CONVERSATIONAL ACTION

A NextBestConversationalAction determines what should happen next.

Possible actions:

ANSWER


ASK


CONFIRM


RECOMMEND


EXECUTE


WAIT


FOLLOW_UP


ESCALATE


TRANSFER


CLOSE
70. NEXT-BEST-ACTION PRINCIPLE

The next best action shall optimize for the Customer's Goal and restaurant constraints.

It shall not automatically optimize for sales.

Example:

Customer:
"My order is an hour late."


Best action:
Resolve service failure.


Not:
Upsell dessert.
71. SALES WITHIN CONVERSATION

Conversational Intelligence may request Sales Intelligence recommendations when appropriate.

Example:

Customer:
"I need dinner for six people."


Sales Intelligence:
Family bundle may fit.


Operational Intelligence:
Bundle available.


Conversational Intelligence:
Determines whether and how to recommend it.
72. RECOMMENDATION RELEVANCE

A recommendation shall consider:

Current Intent.
Customer Preferences.
Current Order.
Budget signals where explicitly known.
Operational availability.
Current Experience state.
Customer restrictions.
73. RECOMMENDATION SUPPRESSION

Sales recommendations should be suppressed when:

Customer is complaining.
Customer is frustrated.
Safety issue exists.
Critical operational problem exists.
Customer explicitly declines recommendations.
Recommendation would delay resolution.
74. CONVERSATIONAL SAFETY

Safety-sensitive statements require elevated handling.

Example:

Customer:
"I have a severe peanut allergy."

This shall trigger appropriate safety-aware context and policies.

AI shall not invent guarantees regarding allergen safety.

75. SAFETY PRECEDENCE

Priority order shall include:

SAFETY


COMPLIANCE


CUSTOMER COMMITMENT


CUSTOMER GOAL


SERVICE QUALITY


COMMERCIAL OPTIMIZATION
76. POLICY-AWARE CONVERSATION

Conversational Intelligence shall consume applicable business policies.

Examples:

Cancellation policy.
Refund policy.
Reservation policy.
Promotion conditions.
Delivery limits.
Payment requirements.

The AI shall not invent policy.

77. POLICY EXPLANATION

Policies should be communicated in understandable language while preserving their actual meaning.

78. HUMAN ESCALATION

Human escalation occurs when AI should not or cannot complete the Goal.

Reasons may include:

LOW_CONFIDENCE


CUSTOMER_REQUEST


POLICY_EXCEPTION


AUTHORIZATION_REQUIRED


SAFETY


COMPLAINT_SEVERITY


PAYMENT_DISPUTE


TECHNICAL_FAILURE


IDENTITY_AMBIGUITY


BUSINESS_EXCEPTION


AI_CAPABILITY_LIMIT
79. ESCALATION PRINCIPLE

Escalation is not failure.

Correct escalation is an intelligent outcome.

80. ESCALATION TARGET

The platform should determine the most appropriate destination.

Potential targets:

HOST


CASHIER


WAITER


KITCHEN


DELIVERY


EVENT_COORDINATOR


MANAGER


ACCOUNTING


MAINTENANCE


CUSTOMER_SERVICE


SPECIALIST
81. SKILL-BASED ROUTING

Escalation should consider:

Intent.
Required capability.
Branch.
Employee role.
Employee availability.
Urgency.
Authorization.
82. ESCALATION BRIEFING

The receiving Employee should receive:

Customer identity


Current Goal


Conversation summary


Current Intent


Relevant Customer history


Relevant Preferences


Relevant Order / Reservation


Current operational context


Customer sentiment


Actions already attempted


Business opportunity


Risk


Reason for escalation


Recommended next action
83. NO-BLIND-TRANSFER PRINCIPLE

ECIP shall not transfer a Conversation without context when relevant context is available.

84. HUMAN CONTINUATION

The Employee shall continue from the existing Conversation state rather than starting a separate disconnected workflow.

85. AI RE-ENTRY

After human intervention, AI may later resume assistance if authorized.

Example:

AI
→ Manager
→ Resolution
→ AI confirms outcome with Customer
86. HUMAN-AI COLLABORATION

Conversation may move dynamically among:

AI-LED


HUMAN-LED


AI-ASSISTED HUMAN


HUMAN-SUPERVISED AI

without losing context.

87. CONVERSATION SUMMARY

A ConversationSummary provides a structured representation of the Conversation.

Potential fields:

Participants.
Goal.
Intents.
Important facts.
Decisions.
Actions.
Commitments.
Open issues.
Sentiment.
Outcome.
88. SUMMARY PRINCIPLE

A summary shall not become a replacement for original evidence.

Original Conversation evidence shall remain available according to retention policy.

89. STRUCTURED EXTRACTION

Conversation may produce structured business information.

Example:

Customer says:


"I need a table for six tomorrow at eight
for my wife's birthday."


        ↓


Reservation Request


party_size = 6
date = resolved tomorrow
time = 20:00
occasion = birthday
90. EXTRACTION CONFIDENCE

Extracted values shall preserve confidence when ambiguity exists.

91. CONVERSATION AS ENTERPRISE SENSOR

Every Conversation may reveal information not currently present in transactional systems.

Examples:

Requested Product not offered


Competitor mentioned


Repeated Customer complaint


Emerging dietary preference


Delivery-area demand


New Event opportunity


Confusing policy


Missing service capability

Conversation therefore acts as an enterprise sensor.

92. CONVERSATIONAL SIGNAL

A ConversationalSignal represents business-relevant information detected from Conversation.

Potential types:

PRODUCT_DEMAND_SIGNAL


UNMET_NEED


CUSTOMER_FRICTION


COMPETITOR_MENTION


PRICE_OBJECTION


PRODUCT_COMPLAINT


SERVICE_COMPLAINT


MENU_CONFUSION


PROMOTION_CONFUSION


EVENT_OPPORTUNITY


LOYALTY_SIGNAL


OPERATIONAL_PROBLEM


EMERGING_TREND
93. SIGNAL VS FACT

Example:

Three Customers ask for vegan desserts.

This creates demand signals.

It does not prove:

"Vegan desserts will be profitable."
94. COMPETITOR MENTION

Conversation may detect mentions of competitors.

Potential information:

Competitor.
Product.
Price.
Service.
Customer comparison.

These shall remain Customer statements unless externally verified.

95. UNMET NEED

An UnmetNeedSignal may be created when Customers repeatedly request unavailable Products or services.

Example:

"Do you have gluten-free pizza?"

Repeated requests may become strategic Menu Intelligence.

96. CUSTOMER FRICTION SIGNAL

Conversation may reveal friction such as:

Confusing Menu.
Difficult ordering process.
Repeated questions.
Payment difficulty.
Long waits.
Unclear promotions.
97. OPERATIONAL SIGNAL FROM CONVERSATION

Customer Conversation may reveal an operational issue before internal systems detect it.

Example:

"The restroom has no water."

Potential flow:

Conversation
    ↓
Operational Signal
    ↓
Validation
    ↓
Operational Incident
98. COMPLAINT DETECTION

Conversational Intelligence may identify complaints and route them to the appropriate domain.

Complaint detection shall preserve:

Original evidence.
Customer statement.
Classification.
Severity.
Confidence.
99. SENTIMENT

Conversation may produce contextual sentiment.

Possible values:

POSITIVE


NEUTRAL


NEGATIVE


MIXED


UNKNOWN

Sentiment is not equivalent to intent.

100. EMOTION / EXPERIENCE CAUTION

AI may estimate conversational affect but shall not treat speculative emotional interpretation as objective fact.

Prefer operationally useful signals such as:

FRUSTRATION_SIGNAL


ESCALATION_SIGNAL


SATISFACTION_SIGNAL

with confidence.

101. CONVERSATION OUTCOME

A ConversationOutcome represents what resulted from the interaction.

Examples:

QUESTION_ANSWERED


ORDER_CREATED


RESERVATION_CREATED


EVENT_LEAD_CREATED


COMPLAINT_RESOLVED


REFUND_REQUESTED


HUMAN_ESCALATION


CUSTOMER_ABANDONED


NO_RESOLUTION
102. BUSINESS OUTCOME

Conversation Outcome may connect to business results.

Examples:

Conversation
    ↓
Order
    ↓
Revenue


Conversation
    ↓
Complaint Resolution
    ↓
Customer Retention


Conversation
    ↓
Event Inquiry
    ↓
Banquet Sale
103. CONVERSATION RESOLUTION

A Conversation is resolved when the relevant Goal has been completed, rejected, cancelled or otherwise conclusively handled.

Ending a call does not necessarily mean resolution.

104. RESOLUTION STATUS

Suggested values:

RESOLVED_SUCCESSFULLY


RESOLVED_PARTIALLY


RESOLVED_WITH_ESCALATION


CUSTOMER_CANCELLED


UNRESOLVED


ABANDONED
105. FIRST-CONTACT RESOLUTION

Potential metric:

Goals resolved without requiring
additional Customer contact
/
Eligible Goals

The definition shall remain explicit.

106. CONVERSATIONAL EFFORT

Potential Customer effort indicators include:

Number of clarification questions.
Number of transfers.
Repeated information.
Number of Sessions.
Time to resolution.
107. CONVERSATIONAL FRICTION

A ConversationFriction may represent unnecessary difficulty during interaction.

Examples:

REPEATED_INFORMATION


EXCESSIVE_CLARIFICATION


MULTIPLE_TRANSFER


LONG_WAIT


FAILED_ACTION


CONTEXT_LOSS


CHANNEL_RESTART
108. CONVERSATION QUALITY

Potential dimensions:

UNDERSTANDING


ACCURACY


RELEVANCE


EFFICIENCY


CONTINUITY


RESOLUTION


CUSTOMER_EFFORT


POLICY_COMPLIANCE


SAFETY
109. CONVERSATIONAL QUALITY SCORE

If implemented, an aggregate score shall remain explainable.

A single score shall not hide Safety or Compliance failures.

110. AI CONFIDENCE

AI confidence may be tracked separately for:

Intent.
Entity resolution.
Response grounding.
Action selection.
Summary.
Signal extraction.

There should not be one meaningless universal confidence value.

111. CONFIDENCE-BASED BEHAVIOR

Low confidence may result in:

ASK_CLARIFICATION


RETRIEVE_MORE_CONTEXT


VERIFY_WITH_DOMAIN


ESCALATE

rather than guessing.

112. HALLUCINATION CONTROL

Conversational Intelligence shall minimize hallucination through:

Authoritative retrieval.
Typed business entities.
Explicit commands.
Policy retrieval.
Confidence handling.
Validation before write.
Output constraints.
Audit evidence.
113. BUSINESS ACTION VALIDATION

Before a write action:

UNDERSTAND REQUEST
        ↓
RESOLVE ENTITY
        ↓
RETRIEVE CURRENT STATE
        ↓
CHECK AUTHORIZATION
        ↓
CHECK POLICY
        ↓
VALIDATE PARAMETERS
        ↓
EXECUTE DOMAIN COMMAND
        ↓
VERIFY RESULT
        ↓
COMMUNICATE CONFIRMATION
114. NO FALSE CONFIRMATION

ECIP shall never tell the Customer:

"Your reservation is confirmed."

unless the authoritative Reservation domain confirms success.

Similarly for:

Order.
Payment.
Refund.
Delivery.
Event.
Cancellation.
115. COMMITMENT CREATION

A Conversation may create a Customer Commitment only after the owning domain confirms it.

116. CONVERSATIONAL COMMITMENT

Conversational Intelligence shall understand promises made during Conversation.

Examples:

"We will call you tomorrow."


"Your refund will be processed."


"Your table is reserved."


"Your order will arrive by 8 PM."

These commitments shall become structured and traceable where material.

117. PROMISE DETECTION

AI may detect potential promises made by Employees or AI.

This can create a CommitmentCandidate.

The appropriate domain validates the Commitment.

118. FOLLOW-UP

A Conversation may create future follow-up requirements.

Examples:

Call Customer.
Send Event proposal.
Confirm Product availability.
Notify when refund completes.
119. FOLLOW-UP OWNERSHIP

Every material follow-up shall have:

Owner.
Due time/date where applicable.
Related Customer.
Related Conversation.
Status.
120. PROACTIVE CONVERSATION

ECIP may initiate authorized conversations.

Examples:

Reservation reminder


Order delay notification


Delivery status


Event follow-up


Service recovery follow-up
121. PROACTIVE CONTACT AUTHORIZATION

Proactive communication shall respect:

Purpose.
Consent.
Channel authorization.
Contactability.
Business policy.
122. CONVERSATION PRIORITY

Conversation priority may consider:

SAFETY


URGENT CUSTOMER COMMITMENT


ACTIVE SERVICE FAILURE


CUSTOMER WAITING


OPERATIONAL URGENCY


BUSINESS VALUE


GENERAL INFORMATION

Commercial value shall not override Safety or urgent service failure.

123. CONCURRENT CONVERSATIONS

ECIP shall support many simultaneous Conversations across Channels.

Conversation state shall remain isolated.

No Customer context may leak between Conversations.

124. MULTI-TENANT ISOLATION

Conversation data shall be isolated by Tenant.

Cross-tenant retrieval is prohibited unless explicitly supported by an authorized platform-level capability.

125. BRANCH CONTEXT

Conversation may be:

Branch-specific.
Organization-wide.
Not yet associated with a Branch.

Branch shall not be guessed when the distinction materially affects the answer.

126. LANGUAGE

Conversational Intelligence should support multiple languages.

Language is presentation/context metadata, not a separate business model.

127. LANGUAGE SWITCHING

A Conversation may switch languages without losing semantic state.

128. TRANSLATION

Translation shall preserve:

Business meaning.
Product names where appropriate.
Quantities.
Dates.
Prices.
Safety information.
Policy meaning.
129. VOICE INTELLIGENCE

Telephone introduces additional processing such as:

Audio Input
    ↓
Speech Recognition
    ↓
Speaker / Turn Processing
    ↓
Conversational Intelligence
    ↓
Semantic Response
    ↓
Speech Generation

Voice is one Channel implementation.

It shall not define the architecture of Conversational Intelligence.

130. SPEECH RECOGNITION UNCERTAINTY

Speech transcription may be uncertain.

Critical values should be confirmed where necessary.

Examples:

Address.
Quantity.
Date.
Time.
Allergy.
Payment-related information.
131. INTERRUPTIONS

Voice Conversations may include:

Interruptions.
Silence.
Overlapping speech.
Background noise.
Dropped calls.

These are Channel concerns that may affect Conversation state.

132. CALL INTERRUPTION RECOVERY

If a Call disconnects unexpectedly, the Conversation may remain resumable.

The Customer should not lose all progress.

133. MESSAGE CHANNEL INTELLIGENCE

Messaging Channels may introduce:

Delayed responses.
Multiple Messages.
Media.
Read receipts.
Interactive buttons.

These shall map to the canonical Conversation Model.

134. ASYNCHRONOUS CONVERSATION

Messaging may remain open for hours or days.

Conversation lifecycle shall therefore not assume real-time interaction.

135. EMPLOYEE CONVERSATIONS

Future ECIP capabilities may support internal Employee Conversations.

Examples:

"Why is table 12 delayed?"


"Do we have enough salmon for tonight?"


"Which deliveries are at risk?"

The same intelligence architecture may serve authorized internal actors.

136. SUPPLIER CONVERSATIONS

Future capabilities may support Supplier interactions.

Examples:

Purchase status.
Delivery confirmation.
Shortage notification.
Invoice question.

Supplier identity and authorization shall remain distinct from Customer identity.

137. AGENT-TO-AGENT CONVERSATION

Future intelligent agents may communicate through structured conversational interfaces.

Examples:

Customer Agent
↔
Restaurant Agent


Restaurant Operations Agent
↔
Supplier Agent

Agent communication shall use the same governed business semantics where appropriate.

138. AGENT IDENTITY

Every autonomous Agent shall have explicit:

Identity.
Tenant.
Role.
Permissions.
Authority.
Audit trail.

An Agent shall never be treated as an anonymous superuser.

139. AGENT AUTHORITY

Conversational capability does not imply business authority.

An Agent may understand a request but still lack permission to execute it.

140. CONVERSATIONAL INTELLIGENCE AS API

The intelligence capability should eventually be consumable independently of any specific user interface.

Conceptually:

Channel
   ↓
Conversation API
   ↓
Conversational Intelligence Runtime
   ↓
Enterprise Intelligence / Domain APIs

This enables future Channels and Agents.

141. CONVERSATIONAL INTELLIGENCE RUNTIME

A future runtime may logically contain:

Conversation Manager


Identity Resolver


Intent Engine


Entity Resolver


Context Orchestrator


Policy Resolver


Business Knowledge Retriever


Conversation Planner


Decision Engine


Action Orchestrator


Response Composer


Escalation Router


Memory Manager


Signal Extractor


Audit Recorder

These are logical responsibilities, not mandatory microservices.

142. CONTEXT ORCHESTRATOR

The Context Orchestrator determines what information is required for current reasoning.

It shall avoid uncontrolled retrieval.

143. BUSINESS KNOWLEDGE RETRIEVER

The Business Knowledge Retriever obtains authorized current information from authoritative domains.

It shall not become a shadow database owner.

144. ACTION ORCHESTRATOR

The Action Orchestrator coordinates authorized business commands.

It shall preserve:

Domain ownership.
Idempotency.
Correlation ID.
Authorization.
Result validation.
145. RESPONSE COMPOSER

The Response Composer transforms the semantic outcome into appropriate Customer-facing communication.

It shall not alter business facts.

146. ESCALATION ROUTER

The Escalation Router determines:

WHO SHOULD HANDLE THIS?


WHERE ARE THEY?


ARE THEY AVAILABLE?


DO THEY HAVE AUTHORITY?
147. MEMORY MANAGER

The Memory Manager determines:

What remains Session context.
What remains Conversation context.
What becomes a long-term memory candidate.
What should expire.
What should not be retained.
148. SIGNAL EXTRACTOR

The Signal Extractor converts Conversation evidence into candidate enterprise signals.

Examples:

Repeated Product Request
Customer Friction
Competitor Mention
Operational Problem
Event Opportunity
149. AUDIT RECORDER

Material conversational decisions and actions shall preserve sufficient evidence for reconstruction.

150. CONVERSATION EVIDENCE

Evidence may include:

Original Message.
Audio reference.
Transcript.
Extracted entities.
Intent.
Context Snapshot.
Retrieved domain facts.
Decision.
Action result.

Retention depends on applicable policy.

151. TRANSCRIPT

A Transcript is an evidence representation of spoken Conversation.

It shall not automatically be treated as perfectly accurate.

152. TRANSCRIPT CORRECTION

Where relevant, corrected transcription may be stored while preserving original evidence and correction provenance.

153. CONVERSATIONAL AUDIT TRAIL

For material Actions, the platform should answer:

What did the Customer ask?


What did ECIP understand?


What context did ECIP retrieve?


What policy applied?


What decision was made?


What command was executed?


What did the authoritative domain return?


What did ECIP tell the Customer?


What happened afterward?
154. PRIVACY

Conversation may contain more personal information than is operationally necessary.

Therefore ECIP shall implement:

Data minimization.
Purpose limitation.
Access control.
Retention.
Tenant isolation.
Auditability.
Redaction where appropriate.
155. SECRET / PAYMENT DATA

Conversational systems shall avoid unnecessarily retaining:

Authentication secrets.
Sensitive Payment credentials.
Full card data.
Other prohibited information.

Secure specialized flows shall be used where required.

156. CONVERSATIONAL REDACTION

Sensitive content may require redaction in:

Transcripts.
Logs.
Analytics.
Training datasets.
Employee views.

Original evidence retention, if legally required, shall remain separately controlled.

157. MODEL TRAINING BOUNDARY

Customer Conversations shall not automatically become unrestricted AI training data.

Any use for model improvement shall follow applicable authorization, privacy and governance.

158. CONVERSATIONAL ANALYTICS

Potential analytics include:

Conversation volume.
Channel volume.
Intent distribution.
Resolution rate.
Escalation rate.
Average resolution time.
Customer effort.
Conversation abandonment.
Sales conversion.
Complaint rate.
Unmet needs.
Emerging topics.
159. INTENT DISTRIBUTION

Potential metric:

Conversations by Intent
/
Total Classified Conversations
160. RESOLUTION RATE

Potential metric:

Resolved Conversations
/
Eligible Conversations

Definitions shall remain explicit.

161. ESCALATION RATE

Potential metric:

Human Escalations
/
Eligible AI-Handled Conversations

A lower escalation rate is not automatically better.

Correct escalation quality matters.

162. CONVERSATION ABANDONMENT RATE

Potential metric:

Abandoned Conversations
/
Started Conversations

Context must distinguish intentional Customer departure from technical failure.

163. CONVERSATIONAL SALES CONVERSION

Potential metric:

Qualified Commercial Conversations
resulting in Transaction
/
Qualified Commercial Conversations

Sales Intelligence remains authoritative for commercial methodology.

164. CUSTOMER EFFORT METRIC

Potential inputs:

Clarifications


Repeated Information


Transfers


Sessions Required


Time to Resolution
165. AI RESOLUTION RATE

Potential metric:

Eligible Goals fully resolved by AI
/
AI-addressable Goals

This shall not encourage unsafe automation.

166. ESCALATION QUALITY

Potential measures:

Correct destination.
Complete briefing.
No unnecessary repetition.
Resolution after transfer.
Transfer time.
167. CONVERSATIONAL SIGNAL ANALYTICS

The platform may aggregate signals such as:

Top requested unavailable Products


Most common complaints


Most confusing Menu Items


Frequent competitor mentions


Emerging Customer needs


Common service friction


Frequent operational issues reported by Customers
168. TREND DETECTION

Conversational Intelligence may detect changes over time.

Example:

Requests for high-protein dishes
increased 240% over 90 days.

This is a demand signal, not automatically a recommendation to change the Menu.

169. EXECUTIVE CONVERSATIONAL INTELLIGENCE

Potential executive questions include:

"What are customers asking for most?"


"What are we failing to answer?"


"Why are customers calling?"


"What complaints are increasing?"


"What products are customers requesting that we don't sell?"


"What competitor is mentioned most?"


"Which conversations generate the most sales?"


"Where are customers experiencing friction?"


"What should management know from today's conversations?"
170. CONVERSATIONAL INTELLIGENCE DASHBOARD

A future logical view may include:

CONVERSATIONS


Active
Resolved
Escalated
Abandoned


CUSTOMER NEEDS


Top Intents
Emerging Intents
Unmet Needs


EXPERIENCE


Complaints
Sentiment
Friction
Resolution


COMMERCIAL


Sales Opportunities
Conversions
Recommendations Accepted


OPERATIONS


Operational Problems Reported
Commitments At Risk


INTELLIGENCE


Emerging Trends
Competitor Mentions
Strategic Signals

This document does not prescribe UI.

171. REAL-TIME CONVERSATION SUPERVISION

Authorized supervisors may need visibility into:

Active Conversations.
Conversations requiring assistance.
High-risk Conversations.
Long-running Conversations.
Escalations.
Safety-related Conversations.

Access shall remain role-controlled.

172. CONVERSATIONAL ALERTS

Potential alerts include:

SAFETY_CONVERSATION_DETECTED


HIGH_SEVERITY_COMPLAINT


CUSTOMER_COMMITMENT_AT_RISK


AI_LOW_CONFIDENCE


REPEATED_AI_FAILURE


ESCALATION_UNAVAILABLE


CUSTOMER_WAITING_TOO_LONG


PAYMENT_DISPUTE


OPERATIONAL_PROBLEM_REPORTED


HIGH_VALUE_EVENT_OPPORTUNITY
173. ALERT FATIGUE

Not every negative sentiment or low-confidence phrase shall create an alert.

Alerts shall be prioritized and deduplicated.

174. CONVERSATIONAL LEARNING LOOP

Conceptually:

CONVERSATION
      ↓
UNDERSTANDING
      ↓
CONTEXT
      ↓
DECISION
      ↓
ACTION
      ↓
CUSTOMER RESPONSE
      ↓
OUTCOME
      ↓
SIGNALS
      ↓
LEARNING
      ↓
BETTER FUTURE CONVERSATION
175. LEARNING BOUNDARY

Learning shall not mean uncontrolled model self-modification.

Learning may update:

Customer knowledge.
Business analytics.
Recommendation effectiveness.
Intent models.
Routing rules.
Knowledge gaps.

Model changes shall follow governed deployment processes.

176. KNOWLEDGE GAP

A ConversationalKnowledgeGap occurs when ECIP repeatedly cannot answer a legitimate business question.

Examples:

Unknown Event policy


Missing Product information


Missing allergen information


Missing Delivery coverage


Unclear Promotion conditions

Knowledge gaps should become actionable enterprise signals.

177. AI FAILURE

An AIFailure may include:

INTENT_FAILURE


ENTITY_FAILURE


CONTEXT_FAILURE


RETRIEVAL_FAILURE


POLICY_FAILURE


ACTION_FAILURE


RESPONSE_FAILURE


HALLUCINATION_DETECTED
178. FAILURE RECOVERY

When AI fails:

DETECT
    ↓
STOP UNSAFE ACTION
    ↓
PRESERVE CONTEXT
    ↓
ESCALATE / RETRY SAFELY
    ↓
RECORD FAILURE
    ↓
LEARN
179. CHANNEL FAILURE

Channel failure shall not necessarily destroy Conversation state.

Example:

Telephone disconnects
        ↓
Conversation remains open
        ↓
Customer resumes through WhatsApp

where identity and policy permit.

180. EXTERNAL SYSTEM FAILURE

If authoritative systems are unavailable, ECIP shall not invent business state.

Example:

Reservation system unavailable.

Correct response may be:

Cannot confirm reservation yet.

rather than falsely confirming it.

181. DEGRADED MODE

ECIP may operate in degraded conversational mode.

Possible capabilities:

GENERAL INFORMATION


MESSAGE CAPTURE


HUMAN ESCALATION


FOLLOW-UP CREATION

while disabling unsafe transactional actions.

182. OBSERVABILITY

Conversational Intelligence shall expose technical and business observability including:

Latency.
Model failures.
Retrieval failures.
Domain-command failures.
Channel failures.
Escalation failures.
Token/model usage where relevant.
Conversation outcomes.
183. TRACEABILITY

A Conversation should have correlation across:

Channel Event


Conversation


AI Request


Context Retrieval


Domain Command


Business Transaction


Response


Outcome
184. CORRELATION ID

Material operations should support correlation identifiers across distributed components.

185. IDEMPOTENCY

Conversational retries shall not accidentally duplicate business Actions.

Example:

Network retry

must not create:

Two Reservations

or:

Two Payments
186. CONCURRENCY

The platform shall protect against conversational race conditions.

Example:

Customer sends:
"Cancel it"


at the same moment an Employee confirms the Order.

Authoritative domain concurrency controls remain necessary.

187. EVENT-DRIVEN CONVERSATION

Business events may update Conversation context.

Example:

Conversation waiting for refund.


Payment domain emits:
RefundCompleted


        ↓


Conversation becomes actionable.


        ↓


Customer can be notified.
188. CONVERSATION SUBSCRIPTION

A Conversation may temporarily subscribe to relevant business events.

Examples:

Payment completion.
Order readiness.
Delivery arrival.
Reservation confirmation.
Manager approval.
189. FUTURE AGENTIC CONVERSATION

Future Intelligent Agents may manage multi-step Goals.

Example:

Customer:
"Organize my daughter's birthday dinner
for 30 people next month."


Agent may:


Understand Goal
    ↓
Collect missing constraints
    ↓
Check availability
    ↓
Explore packages
    ↓
Generate proposal
    ↓
Coordinate approval
    ↓
Create Event
    ↓
Arrange follow-up

Every step remains governed by domain authority.

190. AUTONOMY LEVEL

Future Conversation automation may support levels such as:

L0 — INFORMATION ONLY


L1 — RECOMMEND


L2 — ACT WITH EXPLICIT CONFIRMATION


L3 — ACT WITHIN PREAUTHORIZED POLICY


L4 — MANAGE MULTI-STEP GOALS


L5 — HIGH AUTONOMY WITH GOVERNED EXCEPTIONS

Autonomy level shall be configurable by action/domain.

191. AUTONOMY PRINCIPLE

More autonomy is not automatically better.

The objective is:

Maximum useful autonomy within acceptable risk and authority.

192. CONVERSATIONAL DIGITAL TWIN CONTRIBUTION

Conversational Intelligence contributes to the Restaurant Digital Twin by revealing:

WHAT CUSTOMERS WANT


WHAT EMPLOYEES KNOW


WHAT PEOPLE ARE EXPERIENCING


WHAT THE TRANSACTIONAL SYSTEMS DO NOT CAPTURE


WHAT THE RESTAURANT HAS PROMISED


WHAT PROBLEMS ARE EMERGING


WHAT OPPORTUNITIES ARE APPEARING
193. CONVERSATION AS KNOWLEDGE SOURCE

Traditional restaurant software primarily learns from transactions.

ECIP additionally learns from:

QUESTIONS


REQUESTS


OBJECTIONS


COMPLAINTS


COMPLIMENTS


INTENTIONS


UNFULFILLED NEEDS


CONVERSATIONAL DECISIONS

This is strategically important because many business signals occur before a transaction exists.

194. PRE-TRANSACTION INTELLIGENCE

Example:

Customer asks for Product X.


Restaurant does not sell Product X.


No transaction occurs.

Traditional POS:

Sees nothing.

ECIP:

Records demand signal.

Repeated across Customers:

Potential Menu Opportunity.
195. LOST-DEMAND INTELLIGENCE

Conversational Intelligence can reveal demand that never became Sales.

Examples:

Product unavailable.
Price objection.
Delivery unavailable.
No Reservation availability.
Missing dietary option.
Customer abandoned purchase.

This creates intelligence unavailable from completed Sales alone.

196. LOST CONVERSION REASON

Where evidence exists, Conversation may classify reasons such as:

PRICE


UNAVAILABLE_PRODUCT


NO_CAPACITY


DELIVERY_LIMITATION


POLICY


CUSTOMER_CHANGED_MIND


PAYMENT_FAILURE


COMPETITOR


UNKNOWN
197. CONVERSATION-TO-BUSINESS GRAPH

Long-term ECIP should be able to represent:

Conversation
    │
    ├── Customer
    ├── Intent
    ├── Product
    ├── Order
    ├── Reservation
    ├── Event
    ├── Complaint
    ├── Employee
    ├── Branch
    ├── Commitment
    ├── Opportunity
    ├── Incident
    └── Outcome

This enables enterprise reasoning across conversations and transactions.

198. CONVERSATION HISTORY

The platform shall preserve relevant history while preventing uncontrolled context growth.

Conversation history may be represented through:

Original evidence.
Structured events.
Summaries.
Current state.
Relevant memory.
199. HISTORY COMPACTION

Long Conversations may require semantic compaction.

Conceptually:

RAW HISTORY
    ↓
STRUCTURED EVENTS
    ↓
SUMMARY
    ↓
ACTIVE CONTEXT

Original evidence remains separately governed.

200. SUMMARY VERSIONING

When Conversation summaries change materially, versioning may preserve historical state.

201. CONVERSATION INTELLIGENCE PROFILE

A logical ConversationIntelligenceProfile may compose:

Conversation State


Participants


Goal


Current Intents


Resolved Entities


Relevant Context


Sentiment / Friction Signals


Active Commitments


Open Questions


Recommended Next Action


Escalation State


Related Business Entities

It is a composed intelligence view, not an independent source of truth for all referenced domains.

202. CONVERSATION RISK

A ConversationRisk may represent potential harm or failure.

Examples:

SAFETY_RISK


CUSTOMER_LOSS_RISK


COMMITMENT_FAILURE_RISK


POLICY_RISK


PAYMENT_RISK


AI_ERROR_RISK


ESCALATION_RISK
203. CONVERSATION RISK LEVEL

Suggested levels:

LOW


MODERATE


HIGH


CRITICAL
204. CONVERSATIONAL OPPORTUNITY

A ConversationalOpportunity may represent an actionable opportunity discovered during Conversation.

Examples:

UPSELL


CROSS_SELL


EVENT_LEAD


LOYALTY_ENROLLMENT


CUSTOMER_RECOVERY


NEW_PRODUCT_DEMAND


CORPORATE_ACCOUNT


REACTIVATION
205. OPPORTUNITY QUALIFICATION

Not every mention becomes a qualified opportunity.

Evidence and context are required.

206. BUSINESS SIGNAL AGGREGATION

Individual signals may be aggregated across:

Customers.
Branches.
Products.
Channels.
Time periods.

This transforms Conversations into enterprise intelligence.

207. SIGNAL PROVENANCE

Aggregated intelligence shall remain traceable to underlying evidence where authorized.

208. CONVERSATIONAL INTELLIGENCE EVENTS

Initial domain events include:

ConversationCreated
ConversationStarted
ConversationPaused
ConversationResumed
ConversationResolved
ConversationClosed
ConversationAbandoned


ConversationSessionStarted
ConversationSessionEnded


ParticipantJoinedConversation
ParticipantLeftConversation
ActorIdentityResolved
ActorIdentityConflictDetected


MessageReceived
MessageSent
UtteranceDetected


ConversationalIntentDetected
ConversationalIntentConfirmed
ConversationalIntentChanged
ConversationalIntentUnresolved


ConversationalEntityDetected
ConversationalEntityResolved
ConversationalEntityAmbiguous


ConversationGoalDetected
ConversationGoalUpdated
ConversationGoalCompleted


ConversationContextUpdated
ConversationContextSnapshotCreated


ConversationPlanCreated
ConversationPlanUpdated


ConversationalDecisionCreated
NextBestConversationalActionCreated


ClarificationRequested
ClarificationResolved


ConversationalCommandCreated
ConversationalCommandAuthorized
ConversationalCommandRejected
ConversationalCommandExecuted
ConversationalCommandFailed


ConversationCommitmentCandidateDetected
ConversationFollowUpCreated


ConversationEscalationRequested
ConversationEscalated
ConversationEscalationAccepted
ConversationEscalationFailed


ConversationSummaryCreated
ConversationSummaryUpdated


ConversationalSignalDetected
UnmetNeedDetected
CompetitorMentionDetected
CustomerFrictionDetected
OperationalProblemReported


ConversationOpportunityDetected


ConversationRiskDetected
ConversationRiskEscalated
ConversationRiskResolved


ConversationKnowledgeGapDetected


AIFailureDetected
ConversationChannelFailureDetected


ConversationOutcomeRecorded


ConversationIntelligenceSynchronizationStarted
ConversationIntelligenceSynchronizationCompleted
ConversationIntelligenceSynchronizationFailed
209. RELATIONSHIPS
Actor
    PARTICIPATES_IN Conversation


Conversation
    HAS ConversationSession


ConversationSession
    USES Channel


Conversation
    HAS Message


Message
    MAY_CONTAIN Utterance


Utterance
    EXPRESSES ConversationalIntent


Utterance
    MAY_REFERENCE ConversationalEntity


Conversation
    MAY_HAVE ConversationGoal


Conversation
    HAS ConversationalContext


ConversationalContext
    REFERENCES CustomerIntelligence


ConversationalContext
    REFERENCES OperationalIntelligence


ConversationalContext
    REFERENCES SalesIntelligence


Conversation
    MAY_HAVE ConversationPlan


ConversationPlan
    PRODUCES NextBestConversationalAction


NextBestConversationalAction
    MAY_CREATE ConversationalCommand


ConversationalCommand
    IS_EXECUTED_BY AuthoritativeDomain


Conversation
    MAY_CREATE CommitmentCandidate


Conversation
    MAY_CREATE ConversationalSignal


ConversationalSignal
    MAY_INFORM IntelligenceDomain


Conversation
    MAY_CREATE ConversationalOpportunity


Conversation
    MAY_CREATE ConversationRisk


Conversation
    MAY_ESCALATE_TO Employee


Conversation
    PRODUCES ConversationOutcome


ConversationOutcome
    CONTRIBUTES_TO EnterpriseLearning
210. BUSINESS RULES

The following rules apply:

Conversational Intelligence shall be channel-independent.
Channel adapters shall not own restaurant business logic.
Conversation shall remain distinct from Session, Message and Channel.
Conversations may span multiple Channels.
Actor identity shall remain distinct from Channel identity.
Identity confidence shall constrain disclosure and action.
Intent shall remain distinguishable from Goal.
Multiple Intents may coexist in one Conversation.
Explicit and inferred Intents shall remain distinguishable.
Business entity resolution shall preserve confidence.
Material ambiguity shall trigger clarification rather than guessing.
Conversational context shall be minimized to relevant authorized information.
Mutable business state shall be refreshed before material commitments.
Conversational Intelligence shall not become the source of truth for business domains it consumes.
Business writes shall occur through authoritative domain commands.
Read authority does not imply write authority.
AI understanding does not imply authorization to act.
Material responses shall be grounded in authoritative business information.
Predictions and inferences shall not be represented as facts.
Customer statements shall preserve provenance.
Safety-sensitive information shall receive elevated handling.
Safety and Compliance shall take precedence over commercial optimization.
ECIP shall never falsely confirm an unverified business transaction.
Conversation termination does not necessarily mean Goal resolution.
Human escalation is a valid successful intelligence outcome.
Human escalation shall preserve relevant context.
Blind transfers should be avoided.
Customer information already reliably known should not be requested again unnecessarily.
Conversation memory shall be classified by scope and retention purpose.
Temporary Conversation context shall not automatically become permanent Customer memory.
Long-term memory candidates shall be validated by the appropriate owning domain.
Conversations may generate enterprise signals even when no transaction occurs.
Conversational signals shall remain distinguishable from verified business facts.
Channel failure shall not automatically destroy Conversation state.
External system failure shall not result in invented business state.
Retries shall preserve idempotency.
Multi-tenant Conversation isolation is mandatory.
Conversation evidence shall be retained according to applicable policy.
AI model training shall remain governed separately from operational Conversation storage.
Material Conversational Decisions and Actions shall be auditable.
AI failures shall be observable and recoverable.
The platform shall optimize resolution and Customer value before unnecessary Conversation length.
Sales recommendations shall be contextually appropriate.
Customer dissatisfaction or active service failure should suppress inappropriate selling.
Every Conversation should improve enterprise knowledge only when the resulting knowledge is relevant, legitimate and governed.
211. MVP PRIORITY

For the first production-oriented implementation, prioritize:

Conversation


ConversationSession


ConversationParticipant


ChannelReference


Message


Utterance


ActorReference


CustomerReference


ConversationState


ConversationalIntent


IntentConfidence


ConversationalEntity


EntityResolution


ConversationGoal


ConversationalContext


ConversationContextSnapshot


PendingQuestion


ConversationPlan


NextBestConversationalAction


ConversationalCommand


DomainCommandResult


ConversationCommitmentReference


ConversationSummary


ConversationOutcome


HumanEscalation


EscalationReason


EscalationBriefing


ConversationalSignal


ConversationRisk


ConversationOpportunity


ConversationKnowledgeGap


ExternalConversationMapping


ConversationAuditHistory
212. FIRST PRODUCTION CHANNEL

Telephone may be the first production Channel.

However, implementation shall preserve:

TELEPHONE
        ↓
CHANNEL ADAPTER
        ↓
CANONICAL CONVERSATION
        ↓
CONVERSATIONAL INTELLIGENCE

and not:

TELEPHONE
        ↓
TELEPHONE-SPECIFIC BUSINESS INTELLIGENCE

This distinction is critical for future Channel expansion.

213. FIRST PRODUCTION INTELLIGENCE LOOP

The first implementation should prove this end-to-end loop:

CUSTOMER CONTACT
        ↓
CHANNEL ADAPTER
        ↓
CONVERSATION CREATED / RESUMED
        ↓
CUSTOMER IDENTITY RESOLUTION
        ↓
INTENT + ENTITY UNDERSTANDING
        ↓
RELEVANT BUSINESS CONTEXT RETRIEVED
        ↓
CUSTOMER + OPERATIONAL CONTEXT COMPOSED
        ↓
NEXT-BEST CONVERSATIONAL ACTION
        ↓
RESPONSE / DOMAIN COMMAND / ESCALATION
        ↓
AUTHORITATIVE RESULT
        ↓
CUSTOMER RESPONSE
        ↓
CONVERSATION OUTCOME
        ↓
USEFUL SIGNALS / MEMORY CANDIDATES
        ↓
ENTERPRISE LEARNING

This loop is the fundamental production proof of ECIP.

214. FIRST COMMERCIAL USE CASES

Initial high-value use cases should include:

Restaurant Information


Menu Questions


Product Availability


Product Recommendations


Order Creation


Order Status


Reservations


Reservation Modification


Customer Recognition


Customer Preferences


Complaint Handling


Human Escalation


Operational Status Relevant to Customer


Sales Recommendation


Conversation Continuity


Conversation Summary

These provide sufficient breadth to prove that ECIP is more than a voice assistant.

215. DEFERRED CAPABILITIES

Unless required by the first commercial pilot, defer:

Fully Autonomous Multi-Agent Negotiation


Advanced Emotional Modeling


General-Purpose Employee Copilot


Autonomous Supplier Negotiation


Cross-Enterprise Agent Marketplace


Advanced Conversational Digital Twin Simulation


Self-Modifying Conversation Policies


Reinforcement Learning Dialogue Control


Universal Cross-Business Identity Resolution


Fully Autonomous High-Risk Business Actions


Advanced Multimodal Scene Understanding

These may become strategically valuable later but are not required for the initial production architecture.

216. IMPLEMENTATION PRINCIPLE

This document defines the logical Conversational Intelligence Model.

It does not prescribe:

Telephony provider.
WhatsApp provider.
Speech recognition vendor.
Text-to-speech vendor.
LLM provider.
Vector database.
Agent framework.
Message broker.
Workflow engine.
Programming language.
Microservice topology.
User interface.

Technology decisions shall remain replaceable behind stable contracts.

217. ARCHITECTURAL PRINCIPLE

Conversational Intelligence shall be implemented as an intelligence orchestration layer over authoritative enterprise domains.

Conceptually:

               COMMUNICATION CHANNELS


 Telephone   WhatsApp   Web   App   Kiosk   Future
     │          │        │     │      │       │
     └──────────┴────────┴─────┴──────┴───────┘
                        │
                        ▼
                CHANNEL ADAPTERS
                        │
                        ▼
             CANONICAL CONVERSATION
                        │
                        ▼
          CONVERSATIONAL INTELLIGENCE
                        │
          ┌─────────────┼─────────────┐
          │             │             │
          ▼             ▼             ▼
       CUSTOMER       SALES       OPERATIONAL
     INTELLIGENCE  INTELLIGENCE  INTELLIGENCE
          │             │             │
          └─────────────┼─────────────┘
                        │
                        ▼
               DOMAIN CAPABILITIES
                        │
         ┌──────────────┼──────────────┐
         ▼              ▼              ▼
       ORDERS      RESERVATIONS      EVENTS
         │              │              │
         └──────────────┼──────────────┘
                        │
                        ▼
               AUTHORITATIVE RESULT
                        │
                        ▼
218. STRATEGIC DIFFERENTIATION

Traditional systems generally treat Conversation as:

COMMUNICATION

ECIP shall treat Conversation as:

COMMUNICATION
        +
BUSINESS INTERFACE
        +
INTENT SOURCE
        +
ACTION SOURCE
        +
CUSTOMER KNOWLEDGE SOURCE
        +
OPERATIONAL SENSOR
        +
COMMERCIAL SENSOR
        +
ENTERPRISE KNOWLEDGE SOURCE

This distinction is fundamental to the product.

219. LONG-TERM PRINCIPLE

The long-term objective is not:

Make AI speak naturally with Customers.

The objective is:

Enable the entire restaurant enterprise to understand, remember, reason and act through natural conversation.

The Conversation becomes a universal interface to the business.

A Customer may say:

"I need dinner for my family."

An Employee may say:

"Why are Orders delayed?"

A Manager may say:

"What needs my attention?"

An Owner may eventually say:

"How is my business doing and what should I do?"

All of these interactions should eventually operate over the same governed enterprise intelligence foundation.

220. FINAL RULE

Before ECIP responds, recommends, commits, executes or escalates through a Conversation, it shall be able to determine:

Who is communicating?

How confidently has identity been resolved?

What Channel is being used?

What Conversation does this interaction belong to?

Is there relevant unfinished context?

What is the actor trying to accomplish?

Is the Intent explicit or inferred?

Are multiple Intents present?

What broader Goal exists?

Which business entities are being referenced?

Are any references ambiguous?

What information is already known?

What information is missing?

What information is authoritative fact?

What information is only a Customer statement, observation, inference or prediction?

What Customer context is relevant?

What current operational context is relevant?

What business policies apply?

Is the required information sufficiently fresh?

What is the minimum clarification required?

Can the request be answered without changing business state?

Does the request require a domain command?

Which domain owns that command?

Is the actor authorized?

Is ECIP authorized?

Does the action require explicit confirmation?

Are Safety, Quality or Compliance constraints present?

Can the restaurant actually fulfill what is being requested?

Is a Sales recommendation appropriate?

Should selling be suppressed?

What is the next best conversational action?

Can ECIP safely execute it?

Should a human intervene?

Who is the correct human?

What context must accompany the transfer?

Has the authoritative business result been confirmed?

What should be communicated to the actor?

What Commitment has been created?

Is follow-up required?

Has the Goal actually been resolved?

What useful business signals emerged?

What should remain temporary Conversation context?

What may become governed long-term knowledge?

What was the final business outcome?

Can the complete path from original Conversation through understanding, context, decision, business Action, response and outcome be reconstructed and audited?

Only after these conditions are resolved may ECIP reliably transform Conversation into enterprise Action.

The objective of Conversational Intelligence is not to create a system that talks like a human.

The objective is to create a platform that understands what people mean, understands the business they are interacting with, knows what the business can actually do, safely converts intent into action, preserves continuity across every channel, and transforms every conversation into reusable enterprise intelligence.

That is the capability that turns ECIP from a conversational interface into the conversational brain of the restaurant.
