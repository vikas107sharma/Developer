🧩 Practice Problem — Payment Processing Engine (Fintech-style)

You are building a backend service that processes payments for a platform.

A payment request comes like:

{
  "amount": 1200,
  "currency": "INR",
  "country": "IN",
  "method": "UPI",
  "flow": "collect"
}

Requirements

The system must create the correct payment processor automatically.

But behavior depends on 3 independent axes:

1) payment method
2) country/region
3) payment flow type

Axis 1 — Payment Method

Different logic per method:

Method	Behaviour
UPI	VPA validation + intent/collect
CARD	tokenization + 3DS
NETBANKING	bank redirect
WALLET	balance check
PAYLATER	credit approval
Axis 2 — Region Rules

Regulatory differences:

Country	Rule
India	RBI limits, UPI mandate rules
US	AVS + ZIP validation
EU	PSD2 SCA required
Axis 3 — Flow Type

Payment flow changes behavior:

Flow	Meaning
collect	user approves later (UPI collect)
intent	app switch approval
recurring	mandate / subscription
refund	reverse payment
What You Must Build

Create a system where backend does:

const processor = PaymentProcessorFactory.getProcessor(paymentRequest);

await processor.process();


WITHOUT writing nested condition hell like:

if (method === 'UPI' && country === 'IN' && flow === 'collect') ...
else if (method === 'UPI' && country === 'IN' && flow === 'intent') ...
else if (method === 'CARD' && country === 'EU' && flow === 'recurring') ...

Expected Behavior Examples
Example 1
UPI + India + collect
→ create collect request
→ wait for approval webhook

Example 2
Card + EU + recurring
→ create mandate
→ run SCA
→ store token

Example 3
Wallet + India + refund
→ check wallet balance
→ credit instantly

Constraints

Each processor must encapsulate its own logic

No giant switch statements allowed

Easy to add new country or method

Must not modify existing processors when adding a new one

Factory decides which processor to instantiate

Hint (but not solution)

You will likely need:

Abstract Processor
↓
Method Processors
↓
Region decorators / subclasses
↓
Factory resolver

What makes this Level-3

Because creation depends on:

method × country × flow


Not just one variable.

This is exactly where Factory (often Abstract Factory + Registry) becomes necessary.

If you want, after you try it, send me your design — I’ll review like a real code review and point out scaling issues.