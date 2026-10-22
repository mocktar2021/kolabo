/* THE SUPPORT ADDRESS, AND THERE IS ONE OF IT.

   WHY THIS FILE EXISTS. The address used to be written out four times: twice
   as a literal `mailto:` in components/Layout.tsx, once in the French block of
   lib/guideStrings.ts and once in the English block. Nothing tied the four
   together, so they could disagree, and correcting one meant finding the other
   three. That is not a hypothetical: hello@kolaboafrica.com was published in
   all four places, on every page of the site and in the guide's "write to us"
   section, for as long as it took somebody to notice that no mailbox behind it
   was being read. The guide tells a creator whose payout has not arrived to
   write to this address, so a wrong value here is a user with a money problem
   writing into a void.

   IT IS NOT COPY, which is the second reason it is not in a strings bundle.
   pages/LegalPage.tsx makes this argument about the URLs in the legal
   documents and it applies unchanged to an email address: a translator can
   mangle it, and it would have to be written identically in both language
   blocks anyway, so putting it in either one is duplication wearing a
   translation's clothes. The sentence around it is copy and lives in the
   bundle. The address is a fact and lives here.

   WHY mocktar.com AND NOT THE PRODUCT DOMAIN. This is the mailbox that is
   actually read. kolabo.africa@mocktar.com forwards to a Zoho mailbox on
   mocktar.com, which is also the reply-to on every verification email the
   product sends (MAIL_REPLY_TO, set 15 September), so support mail and the
   replies users send to their own verification emails now land in the same
   place rather than two. An address on kolaboafrica.com would read better and
   is a one line change here when a mailbox on that domain is the one being
   read. Until then, an address that works beats an address that matches.

   IF YOU CHANGE IT, change it here and nowhere else. Both the footer and the
   guide import this constant, and the mobile app publishes no address at
   all. */
export const SUPPORT_EMAIL = "kolabo.africa@mocktar.com";

/* The href, so that no caller writes the scheme out itself. Three call sites
   did, and a `mailto:` typed by hand is a link that silently does nothing when
   the colon is missed. */
export const SUPPORT_MAILTO = `mailto:${SUPPORT_EMAIL}`;
