# Translation and Localization Readiness

English and French are both required at launch. French is the primary language of the pilot markets (Benin and Togo), so French quality is not optional polish, it is a launch requirement.

## Coverage

- [ ] Every user facing string exists in both EN and FR. No hard coded text in the web or mobile apps. Owner: Frontend and mobile.
- [ ] Transactional messages (OTP, notifications, emails) available in both languages and sent in the user's chosen language. Owner: Backend.
- [ ] Contract body available in both languages, matched to the party's country. Owner: Backend plus counsel for the reviewed wording.
- [ ] Error messages and validation text translated, not just happy path screens. Owner: Frontend and mobile.

## Quality

- [ ] Native French speaker review of all FR strings, with attention to West African French usage rather than only European French. Owner: Community plus a native reviewer.
- [ ] Native English speaker review of all EN strings. Owner: Community.
- [ ] Currency, date, and phone number formats render correctly per country (XOF, +229 for Benin, +228 for Togo). Owner: Frontend and mobile.
- [ ] Name and address fields accept local formats. Owner: Frontend and mobile.

## Process

- [ ] A single source of truth for strings (translation keys) so a missing translation is visible and cannot silently fall back to the wrong language. Owner: Engineering.
- [ ] A defined path to add a language for future markets (for example Twi or Pidgin considerations for Ghana and Nigeria) without a code change to existing screens. Owner: Engineering.

## Founder approval required

- [ ] Sign off that the French experience is good enough to represent the brand in the pilot markets.
