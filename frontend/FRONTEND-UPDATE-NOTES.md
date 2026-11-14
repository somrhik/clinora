# Clinora frontend update

## What changed
- Patient state field is now an India State / Union Territory dropdown.
- Required fields display a red asterisk and retain native HTML validation.
- Home hero rotates through four healthcare images every five seconds, with manual slide dots.
- Added a three-image editorial strip, expanded FAQ to five questions, and added subtle color treatments.
- Updated contact email to clinora.health@gmail.com.
- Improved the patient login gate with a doctor image and patient/doctor login paths.
- Existing doctor booking flow retains its live available-slot API and now has clearer slot styling.
- Added the supplied React Bits `MaskedHeading` and `StarBorder` components.

## Install
From the frontend directory:
```bash
npm install
npm run dev
```
`gsap` is now listed as a dependency for MaskedHeading. `npm install` updates package-lock.json.

## React Bits Pro
Auth 4 and Scheduling 7 are Pro registry blocks and need an active React Bits Pro license key.
This update does not install or claim to include those paid blocks. The login gate and booking slot UI are custom equivalents styled for Clinora.
