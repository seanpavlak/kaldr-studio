import { useEffect, type ReactNode } from 'react'
import { Logo } from './pixel.tsx'

function Page({ title, meta, children }: { title: string; meta?: ReactNode; children: ReactNode }) {
  useEffect(() => {
    document.title = `${title} · KALDR STUDIO`
  }, [title])
  return (
    <div className="legal">
      <header>
        <a className="brand" href="/">
          <Logo />
          <span className="mark">Kaldr Studio</span>
          <span className="subtitle">Back to the studio</span>
        </a>
      </header>
      <article>
        <h1>{title}</h1>
        {meta ?? <p className="dated">October 24, 2026</p>}
        {children}
      </article>
    </div>
  )
}

export function Terms() {
  return (
    <Page
      title="Terms of Service"
      meta={(
        <>
          <p className="dated"><strong>Kaldr Studio</strong></p>
          <p className="dated">Effective Date: October 24, 2026</p>
          <p className="dated">Last Updated: October 29, 2026</p>
        </>
      )}
    >
      <p>Welcome to Kaldr Studio.</p>
      <p>These Terms of Service (“Terms”) govern your access to and use of Kaldr Studio, including its Sprite Builder, artificial intelligence-assisted image generation, proprietary image-processing tools, animation features, downloads, and related services (collectively, the “Service”).</p>
      <p>Kaldr Studio Cloud is operated by Kaldr Industries LLC (“Kaldr Studio,” “we,” “us,” or “our”).</p>
      <p>Kaldr Studio can also be self-hosted. A self-hosted copy is operated by whoever runs it, not by Kaldr Industries LLC. We do not run, monitor, or control self-hosted copies and are not responsible for how they are operated or what they do with your data.</p>
      <p>By accessing or using the Service, you agree to these Terms and acknowledge our <a href="/privacy">Privacy Policy</a>. If you do not agree, do not use the Service.</p>
      <p>Nothing in these Terms limits rights or remedies that cannot lawfully be waived.</p>

      <h2>1. Description of the Service</h2>
      <p>Kaldr Studio provides software tools for creating, transforming, editing, animating, and exporting digital sprite assets, and for turning a recording into a vocal-free loop.</p>
      <p>The Service may include:</p>
      <ul>
        <li>Uploading reference images and artwork.</li>
        <li>Generating AI-assisted redraws through third-party models.</li>
        <li>Transforming images into pixel-art sprites using proprietary processing algorithms.</li>
        <li>Producing sprite sheets, animation frames, and idle animations.</li>
        <li>Adjusting or regenerating locally processed assets.</li>
        <li>Exporting downloadable digital asset packages.</li>
        <li>Making one sprite, or a batch of sprites from several images or URLs.</li>
        <li>Turning a recording into a vocal-free loop, or a line of text into beep speech. Audio stays on this machine. It does not send that audio or text to OpenRouter, and it never includes a vocal.</li>
        <li>Connecting to third-party AI services through user-provided API credentials.</li>
      </ul>
      <p>Certain operations are performed locally on the user’s device, while others require communication with external service providers.</p>
      <p>Kaldr Studio may modify, replace, suspend, or discontinue features, supported models, processing methods, or integrations, subject to applicable law.</p>
      <p>We do not guarantee that any particular feature, output format, or third-party integration will remain available indefinitely.</p>

      <h2>2. Eligibility and Acceptable Use</h2>
      <p>You must have the legal capacity to enter into these Terms or have appropriate authorization from a parent or legal guardian where permitted by applicable law.</p>
      <p>You agree to use the Service only for lawful purposes.</p>
      <p>You may not:</p>
      <ul>
        <li>Use the Service to create, distribute, or facilitate unlawful content or activities.</li>
        <li>Submit material without the rights or lawful authorization necessary for the requested processing.</li>
        <li>Infringe another party’s copyright, trademark, privacy, publicity, or other legal rights.</li>
        <li>Attempt to compromise, disrupt, or gain unauthorized access to the Service or its infrastructure.</li>
        <li>Introduce malicious code or intentionally interfere with normal Service operations.</li>
        <li>Circumvent technical safeguards or abuse third-party API integrations.</li>
        <li>Use generated or transformed content in a manner that violates applicable law.</li>
      </ul>
      <p>You are responsible for ensuring that your use of the Service complies with applicable laws, regulations, and third-party agreements.</p>

      <h2>3. User-Provided Content</h2>
      <p>You retain whatever ownership and intellectual property rights you already possess in images, artwork, prompts, and other materials you submit to the Service (“User Content”).</p>
      <p>By submitting User Content, you represent and warrant that you possess the rights, licenses, permissions, or other lawful authority necessary to authorize the requested processing.</p>
      <p>Before making a loop, you must confirm that you own each recording or have permission to use it. That confirmation is your representation under this section. Removing the vocals does not remove the rights in the song: its melody, chords, and other musical elements remain protected, and a loop made from a recording you have no rights to may infringe them.</p>
      <p>You grant Kaldr Studio a limited, nonexclusive authorization to access, process, transform, and store User Content as reasonably necessary to provide the Service.</p>
      <p>Where you initiate an operation requiring external AI processing, you also authorize transmission of the necessary User Content to OpenRouter and the selected model provider.</p>
      <p>This authorization does not transfer ownership of User Content to Kaldr Studio.</p>
      <p>Kaldr Studio does not claim ownership of your original artwork merely because you process it using the Service.</p>

      <h2>4. AI-Generated and Transformed Content</h2>
      <p>Kaldr Studio provides artificial intelligence-assisted generation and proprietary image-processing tools that may redraw, transform, pixelate, animate, or otherwise modify user-provided images.</p>
      <p><strong>Kaldr Studio makes no representation or warranty that any transformation, whether performed through artificial intelligence, proprietary algorithms, automated scripts, or a combination thereof, produces a work sufficiently original or legally distinct to avoid infringement of existing intellectual property rights.</strong></p>
      <h3>4.1 No Presumption of Originality or Noninfringement</h3>
      <p>The modification of an existing image does not necessarily create an independently copyrightable work or eliminate intellectual property rights associated with the original material.</p>
      <p>Changes to an image’s resolution, dimensions, color palette, composition, visual style, animation, or other characteristics do not, by themselves, establish that the resulting work is legally distinguishable from its source.</p>
      <p>Kaldr Studio does not represent that its processing methods satisfy any legal standard for originality, transformative use, fair use, or noninfringement.</p>
      <p>Whether a resulting work qualifies for copyright protection, constitutes an unauthorized derivative work, or infringes third-party rights depends on the particular circumstances and applicable law.</p>
      <h3>4.2 User Responsibility and Source Materials</h3>
      <p>You are responsible, to the extent permitted by applicable law, for ensuring that you possess the rights, licenses, permissions, or other lawful basis necessary to submit, transform, reproduce, distribute, or commercially exploit any source material and resulting output.</p>
      <p>By submitting an image, you represent that you have the legal authority to authorize the processing you request.</p>
      <p><strong>You acknowledge that using Kaldr Studio to transform copyrighted material does not grant you a license to that material or otherwise authorize uses that would be unlawful without the rights holder’s permission or another valid legal basis.</strong></p>
      <h3>4.3 Rights in Generated and Transformed Assets</h3>
      <p>As between you and Kaldr Studio, we do not claim ownership of your original User Content or of generated and transformed assets solely by reason of their creation through the Service.</p>
      <p>To the extent Kaldr Studio possesses transferable intellectual property rights in generated output, we grant you a worldwide, perpetual, nonexclusive, royalty-free license to use, reproduce, modify, distribute, and commercially exploit that output.</p>
      <p>This license applies only to rights Kaldr Studio actually possesses and is legally authorized to grant.</p>
      <p>It does not convey ownership of, or any license to, third-party intellectual property incorporated into, depicted in, or otherwise implicated by the resulting content.</p>
      <p>Nor does it establish that any generated or transformed content qualifies for independent copyright protection.</p>
      <h3>4.4 Commercial Use</h3>
      <p>Kaldr Studio does not impose an additional commercial-use restriction on assets generated through the Service, subject to these Terms.</p>
      <p>However, permission from Kaldr Studio to use an output commercially does not constitute legal clearance of that output.</p>
      <p>You are responsible for determining whether your intended use requires additional permissions or licenses, including those arising from the source material or applicable third-party AI provider terms.</p>
      <h3>4.5 No Intellectual Property Clearance</h3>
      <p>Kaldr Studio does not conduct copyright clearance, trademark searches, similarity analysis, ownership verification, or legal review of submitted or generated content.</p>
      <p>The Service is not intended to provide legal advice or determine whether an image may lawfully be used, modified, reproduced, or distributed.</p>
      <p><strong>No particular degree of visual alteration, technical processing, or AI involvement is represented by Kaldr Studio as sufficient to avoid infringement or establish fair use.</strong></p>

      <h2>5. Third-Party Artificial Intelligence Services</h2>
      <p>Kaldr Studio integrates with OpenRouter to provide access to third-party artificial intelligence models.</p>
      <p>By using AI generation features, you acknowledge that:</p>
      <ol>
        <li>Your generation requests may be transmitted to OpenRouter and the selected model provider.</li>
        <li>These providers operate under their own terms, privacy policies, and technical practices.</li>
        <li>Third-party providers may impose independent restrictions on content, usage, retention, availability, and billing.</li>
        <li>Kaldr Studio does not control third-party processing, model behavior, data retention, or billing decisions.</li>
      </ol>
      <p>You are responsible for reviewing and complying with the terms applicable to your selected AI provider.</p>
      <p>Relevant policies include:</p>
      <ul>
        <li><a href="https://openrouter.ai/terms" target="_blank" rel="noopener">OpenRouter Terms of Service</a></li>
        <li><a href="https://openrouter.ai/privacy" target="_blank" rel="noopener">OpenRouter Privacy Policy</a></li>
      </ul>
      <p>Kaldr Studio does not guarantee the accuracy, originality, legality, availability, or reliability of third-party AI services.</p>

      <h2>6. Bring Your Own API Key</h2>
      <p>Kaldr Studio uses a Bring Your Own Key (“BYOK”) model for accessing AI generation services.</p>
      <p>Users supply their own OpenRouter API credentials and authorize the Service to use those credentials for requested operations.</p>
      <h3>6.1 Credential Storage</h3>
      <p>API credentials are stored locally on the device running the application, in a configuration file outside individual project directories.</p>
      <p>The application uses file permissions intended to restrict access to the operating system user account.</p>
      <p>API credentials are not intentionally embedded in exported sprite packages.</p>
      <p>Local file permissions and visual masking do not constitute encryption or guarantee protection against unauthorized access.</p>
      <h3>6.2 API Usage and Charges</h3>
      <p>When you initiate AI generation, your OpenRouter account may incur charges.</p>
      <p>These charges are assessed by OpenRouter according to its pricing and billing policies.</p>
      <p><strong>Kaldr Studio does not pay, reimburse, guarantee, or independently enforce spending limits on your OpenRouter account.</strong></p>
      <p>You are responsible for monitoring usage, configuring spending limits, and managing your OpenRouter account.</p>
      <p>Spending-limit information displayed by Kaldr Studio is informational only and may be incomplete, delayed, or inaccurate.</p>
      <p>Each redraw is a separate charge to your OpenRouter key, including a retry or a redraw of one sprite in a batch. A remaining-budget warning is informational and can be missing or wrong.</p>
      <h3>6.3 Credential Security</h3>
      <p>You are responsible for maintaining the confidentiality and security of your API credentials.</p>
      <p>We recommend using a dedicated API key with an appropriate spending limit.</p>
      <p>If you suspect unauthorized access, you should revoke or rotate the affected credentials directly through OpenRouter.</p>
      <p>Kaldr Studio does not guarantee that credentials cannot be exposed through compromised devices, malicious software, operating system vulnerabilities, or other security incidents.</p>

      <h2>7. Pay What You Want Pricing</h2>
      <p>Kaldr Studio offers downloadable sprite packages using a Pay What You Want (“PWYW”) pricing model.</p>
      <p>Users may select an available contribution amount, including $0 where offered.</p>
      <p>For a batch, the offered amounts are $0, $1, $2, or $5 multiplied by the number of successfully rendered sprites included in that package. A $0 contribution is still allowed.</p>
      <h3>7.1 Voluntary Contributions</h3>
      <p>Unless explicitly stated otherwise during checkout, contributions are voluntary and do not purchase additional ownership rights, exclusive licenses, or guarantees regarding generated content.</p>
      <p>Selecting a higher contribution amount does not provide preferential intellectual property rights or additional warranties.</p>
      <p>A $0 contribution does not reduce the usage rights otherwise granted under these Terms.</p>
      <h3>7.2 Payment Processing</h3>
      <p>Paid contributions are processed through Stripe, an independent third-party payment processor.</p>
      <p>By completing a payment, you authorize Stripe to process the selected transaction according to its applicable terms and policies.</p>
      <p>Stripe may collect payment information, billing details, transaction metadata, and information necessary for fraud prevention and regulatory compliance.</p>
      <p>Kaldr Studio does not directly collect or store complete payment card numbers or card security codes.</p>
      <p>See the <a href="https://stripe.com/privacy" target="_blank" rel="noopener">Stripe Privacy Policy</a>.</p>
      <h3>7.3 Payment Authorization</h3>
      <p>By submitting a payment, you authorize the selected payment method to be charged the amount disclosed during checkout.</p>
      <p>Any applicable taxes or additional charges will be disclosed where required by law.</p>
      <p>Unless expressly stated otherwise, PWYW contributions are one-time payments and do not establish recurring subscriptions.</p>
      <h3>7.4 Refunds</h3>
      <p>Because sprite packages are digital products delivered electronically, completed voluntary contributions are generally nonrefundable once the associated download has been made available, except where required by applicable law.</p>
      <p>If a technical failure prevents access to a paid download, users may contact Kaldr Studio to request assistance or a refund review.</p>
      <p>Nothing in this section limits statutory refund rights or applicable consumer protections.</p>
      <h3>7.5 Free Downloads</h3>
      <p>Where a $0 contribution is available, users may download eligible assets without submitting payment card information.</p>
      <p>Free downloads are subject to the same intellectual property provisions and usage limitations as paid downloads.</p>

      <h2>8. Downloads and Digital Assets</h2>
      <p>The Service allows users to export generated and transformed artwork, sprite sheets, and animation assets as downloadable packages.</p>
      <p>A batch package contains only the sprites that completed. Sprites that failed are left out.</p>
      <p>You are responsible for:</p>
      <ul>
        <li>Downloading and maintaining your own copies.</li>
        <li>Verifying that exported files meet your technical requirements.</li>
        <li>Backing up assets you wish to preserve.</li>
        <li>Ensuring compatibility with your intended software or game engine.</li>
        <li>Confirming that your intended use complies with applicable intellectual property laws.</li>
      </ul>
      <p>Kaldr Studio does not guarantee permanent storage, continued availability, or future recovery of generated assets.</p>
      <p>Downloading or purchasing access to a digital file does not transfer ownership of any third-party intellectual property contained in that file.</p>

      <h2>9. Local Storage and Data Loss</h2>
      <p>Certain Service operations rely on files stored locally on your device.</p>
      <p>These files may be affected by operating system behavior, hardware failures, application errors, user actions, backups, or other software.</p>
      <p>Kaldr Studio does not guarantee that locally stored projects, images, API credentials, or exported assets will remain available or recoverable.</p>
      <p>You are responsible for maintaining appropriate backups.</p>
      <p>For information about storage and processing practices, see our <a href="/privacy">Privacy Policy</a>.</p>

      <h2>10. Kaldr Studio Intellectual Property</h2>
      <p>Kaldr Studio retains all rights it possesses in the Service itself, including its original software, proprietary processing algorithms, scripts, interface designs, branding, logos, documentation, and other protected materials.</p>
      <p>The source code of Kaldr Studio is made available under the Functional Source License, Version 1.1, ALv2 Future License (FSL-1.1-ALv2). That license, not these Terms, governs copying, modifying, and redistributing the source code. It does not permit offering the software, or a modified version of it, as a commercial product or service that competes with Kaldr Studio or Kaldr Studio Cloud.</p>
      <p>Except as permitted by that license or by applicable law, you may not reproduce, redistribute, sublicense, or commercially exploit proprietary elements of the Service without authorization.</p>
      <p>“Kaldr,” “Kaldr Studio,” “Kaldr Studio Cloud,” “Gant,” “Keepers,” Blobert, and the Kaldr logos are trademarks of Kaldr Industries LLC. No license or these Terms grants you the right to use them, except as described in our trademark policy.</p>
      <p>These restrictions do not apply to independently owned User Content or generated assets licensed under Section 4.</p>
      <p>Nothing in these Terms restricts rights granted under applicable open-source software licenses or rights that cannot lawfully be restricted.</p>

      <h2>11. Third-Party Materials and Integrations</h2>
      <p>The Service may incorporate or depend on third-party software, libraries, APIs, payment processors, and other integrations.</p>
      <p>These components may be subject to separate licenses, terms, and policies.</p>
      <p>Kaldr Studio does not guarantee the availability, security, performance, or reliability of third-party services.</p>
      <p>We may modify, replace, or discontinue integrations when reasonably necessary for technical, operational, security, or business reasons.</p>

      <h2>12. Service Availability and Modifications</h2>
      <p>Kaldr Studio is provided as an evolving software service.</p>
      <p>We may update, modify, suspend, or discontinue features, supported models, integrations, or the Service itself.</p>
      <p>We do not guarantee continuous availability or compatibility with future operating systems, browsers, third-party APIs, or hardware configurations.</p>
      <p>Where applicable law requires advance notice or other protections, we will comply with those requirements.</p>

      <h2>13. Disclaimer of Warranties</h2>
      <p><strong>TO THE MAXIMUM EXTENT PERMITTED BY APPLICABLE LAW, THE SERVICE IS PROVIDED “AS IS” AND “AS AVAILABLE,” WITHOUT WARRANTIES OF ANY KIND, WHETHER EXPRESS, IMPLIED, OR STATUTORY.</strong></p>
      <p>This includes, to the extent legally permitted, implied warranties of merchantability, fitness for a particular purpose, title, and noninfringement.</p>
      <p>Kaldr Studio does not warrant that:</p>
      <ul>
        <li>The Service will be uninterrupted, error-free, or secure.</li>
        <li>Generated or transformed content will be original, unique, copyrightable, or noninfringing.</li>
        <li>AI generation or proprietary processing will produce any particular result.</li>
        <li>Altering an image will eliminate existing copyright or other intellectual property restrictions.</li>
        <li>Third-party services will remain available.</li>
        <li>API credentials will be immune from compromise.</li>
        <li>Exported assets will satisfy particular technical, artistic, or commercial requirements.</li>
        <li>Data loss, corruption, or unauthorized access will never occur.</li>
      </ul>
      <p>Some jurisdictions do not permit certain warranty exclusions, so portions of this section may not apply to you.</p>

      <h2>14. Limitation of Liability</h2>
      <p>To the maximum extent permitted by applicable law, Kaldr Studio and its operators, officers, employees, contractors, and affiliates will not be liable for indirect, incidental, special, consequential, exemplary, or punitive damages arising from or related to use of the Service.</p>
      <p>This includes, where legally permitted, losses involving:</p>
      <ul>
        <li>Lost profits, revenue, or business opportunities.</li>
        <li>Loss or corruption of project files.</li>
        <li>Unauthorized access to API credentials.</li>
        <li>Third-party AI usage charges.</li>
        <li>Service interruptions or failures.</li>
        <li>Intellectual property disputes involving source materials, generated content, or transformed assets.</li>
        <li>Inability to access or use exported assets.</li>
      </ul>
      <p><strong>To the maximum extent permitted by applicable law, Kaldr Studio’s aggregate liability arising from or relating to the Service will not exceed the greater of (a) the amount you paid directly to Kaldr Studio during the twelve months preceding the event giving rise to the claim or (b) US $100.</strong></p>
      <p>This limitation applies regardless of the legal theory asserted, except where applicable law prohibits such a limitation.</p>
      <p>Nothing in these Terms excludes or limits liability that cannot lawfully be excluded or limited, including liability for fraud, willful misconduct, or other nonexcludable obligations.</p>

      <h2>15. Indemnification</h2>
      <p>To the extent permitted by applicable law, you agree to indemnify and hold harmless Kaldr Studio and its operators, employees, contractors, and affiliates against third-party claims, damages, liabilities, and reasonable legal expenses arising from:</p>
      <ul>
        <li>Your unlawful use of the Service.</li>
        <li>Your infringement of third-party intellectual property rights.</li>
        <li>User Content submitted without necessary authorization.</li>
        <li>Your distribution or commercial exploitation of infringing generated or transformed content.</li>
        <li>Your material violation of these Terms.</li>
      </ul>
      <p>This obligation applies only to the extent the relevant claim results from your conduct and does not require you to indemnify Kaldr Studio for its own unlawful conduct.</p>

      <h2>16. Suspension and Termination</h2>
      <p>We may suspend or restrict access to the Service where reasonably necessary to address security threats, unlawful activity, abuse, or material violations of these Terms.</p>
      <p>You may stop using the Service at any time.</p>
      <p>Termination does not automatically revoke rights already granted to you in lawfully generated and downloaded assets under Section 4.</p>
      <p>Provisions that by their nature should survive termination, including intellectual property provisions, warranty disclaimers, limitations of liability, indemnification, and dispute-related terms, will continue to apply where legally enforceable.</p>

      <h2>17. Governing Law and Disputes</h2>
      <p>These Terms are governed by the laws of the state in which Kaldr Industries LLC is organized, excluding conflict-of-law principles, except where mandatory consumer protection laws require otherwise.</p>
      <p>Any dispute arising from these Terms will be subject to the jurisdiction of courts having lawful authority over the parties and the dispute.</p>
      <p>Nothing in these Terms prevents users from exercising rights available under applicable consumer protection laws.</p>

      <h2>18. Changes to These Terms</h2>
      <p>Kaldr Studio may revise these Terms to reflect changes in functionality, legal requirements, business operations, or third-party services.</p>
      <p>Updated Terms will be published with a revised “Last Updated” date.</p>
      <p>Where required by law, we will provide additional notice or obtain consent before material changes take effect.</p>
      <p>Continued use of the Service after updated Terms become effective constitutes acceptance only to the extent permitted by applicable law.</p>

      <h2>19. Severability and Entire Agreement</h2>
      <p>If any provision of these Terms is found unenforceable, the remaining provisions will remain effective to the extent permitted by law.</p>
      <p>These Terms, together with the Privacy Policy and any additional terms expressly presented for specific features, constitute the agreement governing your use of the Service.</p>
      <p>Failure to enforce a provision does not constitute a waiver of the right to enforce it later.</p>

      <h2>20. Contact</h2>
      <p>For questions concerning these Terms, payment issues, intellectual property concerns, or legal inquiries, contact Kaldr Industries LLC using the contact information published on the Service’s official website.</p>

      <div className="close">
        <p><strong>Kaldr Studio</strong></p>
        <p className="tagline">Create. Animate. Export.</p>
      </div>
    </Page>
  )
}

export function Privacy() {
  return (
    <Page
      title="Privacy Policy"
      meta={(
        <>
          <p className="dated"><strong>Kaldr Studio</strong></p>
          <p className="dated">Effective Date: October 24, 2026</p>
          <p className="dated">Last Updated: October 29, 2026</p>
        </>
      )}
    >
      <p>Kaldr Studio Cloud is operated by Kaldr Industries LLC (“Kaldr Studio,” “we,” “us,” or “our”). This Privacy Policy applies to Kaldr Studio Cloud. A self-hosted copy of Kaldr Studio is operated by whoever runs it, and Kaldr Industries LLC receives no data from it.</p>
      <p>Kaldr Studio respects your privacy and believes users should understand how their information is collected, processed, stored, and shared.</p>
      <p>This Privacy Policy describes the data practices associated with Kaldr Studio, including its Sprite Builder, Audio Builder, AI-assisted image generation, proprietary image-processing tools, animation features, downloads, and payment integrations (collectively, the “Service”).</p>
      <p>Kaldr Studio is designed to perform substantial portions of its functionality locally on your device. Certain features require communication with third-party providers, including OpenRouter for artificial intelligence processing and Stripe for payments.</p>
      <p>The Service does not require account registration.</p>
      <p>By using the Service, you acknowledge the practices described in this Privacy Policy. Your use of the Service is also governed by our <a href="/terms">Terms of Service</a>.</p>

      <h2>1. Information We Collect and Process</h2>
      <p>Depending on how you use the Service, Kaldr Studio may process the following categories of information:</p>
      <ul>
        <li><strong>User-provided content:</strong> Reference images, artwork, prompts, and other materials submitted for processing.</li>
        <li><strong>Audio:</strong> Recordings, web addresses used to fetch a recording, short text for beep speech, and the vocal-free loops made from them. These stay on this machine and are not sent to OpenRouter.</li>
        <li><strong>Generated content:</strong> AI-generated redraws, transformed sprites, sprite sheets, animation frames, and exported assets.</li>
        <li><strong>Generation settings:</strong> Model selections, processing configurations, and instructions necessary to generate or modify content.</li>
        <li><strong>API credentials:</strong> OpenRouter API keys voluntarily provided by users.</li>
        <li><strong>Local application data:</strong> Configuration files, project files, and other information required for application functionality.</li>
        <li><strong>Payment information:</strong> Limited transaction information received from Stripe, where applicable.</li>
      </ul>
      <p>Kaldr Studio does not require users to provide their name, email address, or other identifying information to access its core sprite-generation features.</p>
      <p>However, Stripe may request personal or billing information when processing paid contributions.</p>
      <p>We do not sell user-provided images, generated artwork, prompts, or API credentials.</p>

      <h2>2. Local Data Storage</h2>
      <p>Kaldr Studio stores project-related files locally on the device running the application.</p>
      <p>These files may include:</p>
      <ul>
        <li>Original reference images.</li>
        <li>AI-generated redraws.</li>
        <li>Transformed sprite images.</li>
        <li>Animation frames and sprite sheets.</li>
        <li>Intermediate processing files.</li>
        <li>Application configuration and project settings.</li>
      </ul>
      <p>Local storage does not guarantee confidentiality, encryption, or permanent availability.</p>
      <p>Locally stored information may be accessible to other applications, individuals with access to the device or operating system account, backup and synchronization services, or software operating with sufficient permissions.</p>
      <p>Kaldr Studio does not guarantee that locally stored information is isolated from other applications or protected against unauthorized access.</p>
      <p>Users are responsible for securing their devices and managing their locally stored files.</p>

      <h2>3. OpenRouter API Credentials</h2>
      <p>Certain features require users to provide their own OpenRouter API key.</p>
      <h3>3.1 Credential Storage</h3>
      <p>When a user saves an API key, the key is stored locally on the user’s Mac in a configuration file outside individual project directories.</p>
      <p>The application uses file permissions intended to restrict access to the operating system user account.</p>
      <p>API keys are not intentionally embedded in generated sprite files or exported project packages.</p>
      <p>After a key is saved, the application displays only a partially masked representation.</p>
      <p><strong>Local file permissions and visual masking are not equivalent to encryption or a guarantee of credential security.</strong></p>
      <h3>3.2 Credential Transmission</h3>
      <p>Kaldr Studio transmits API credentials to OpenRouter when necessary to perform authorized operations, including:</p>
      <ol>
        <li>Submitting AI generation requests.</li>
        <li>Checking API key spending-limit information when a key is saved.</li>
        <li>Checking API key spending-limit information when the application opens with a previously saved key.</li>
        <li>Checking the remaining limit before a confirmed batch, retry, or individual redraw.</li>
      </ol>
      <p>Spending-limit information is used to provide informational warnings.</p>
      <p>A budget check may also read the remaining limit reported for the key.</p>
      <p>Kaldr Studio does not intentionally persist the usage figures or the remaining-limit figure returned by these checks.</p>
      <h3>3.3 Credential Security</h3>
      <p>Kaldr Studio does not guarantee that API credentials cannot be intercepted, copied, exposed, or accessed by unauthorized software or individuals.</p>
      <p>We recommend using a dedicated OpenRouter API key with an appropriate spending limit.</p>
      <p>If you suspect that your credentials have been compromised, you should revoke or rotate the affected key directly through OpenRouter.</p>
      <p>Users remain responsible for charges incurred through their OpenRouter accounts, subject to OpenRouter’s applicable terms and policies.</p>

      <h2>4. Third-Party AI Processing</h2>
      <p>When you initiate an AI generation request, Kaldr Studio transmits information necessary to fulfill that request to OpenRouter.</p>
      <p>This may include:</p>
      <ul>
        <li>The reference image you provide.</li>
        <li>Generation prompts and instructions.</li>
        <li>The selected AI model.</li>
        <li>Your OpenRouter API credentials for authentication.</li>
      </ul>
      <p>A batch sends each image that is redrawn. A retry or a redraw of one sprite sends that image again. Images that are not redrawn are not sent again.</p>
      <p>Audio does not use OpenRouter. A recording and the text for beep speech stay on this machine. A web address is downloaded here first. The voice in a recording is not included in the loop.</p>
      <p>OpenRouter may route requests to the third-party model provider selected for generation.</p>
      <p>These providers operate independently and may process, retain, log, or otherwise handle submitted information according to their own terms, privacy policies, and technical practices.</p>
      <p>Kaldr Studio does not control or guarantee:</p>
      <ul>
        <li>Whether third-party providers retain submitted images or prompts.</li>
        <li>Whether submitted information is used for model training or service improvement.</li>
        <li>The geographic location of third-party processing.</li>
        <li>Third-party security practices or retention periods.</li>
        <li>The availability or reliability of third-party services.</li>
      </ul>
      <p>Users should avoid submitting confidential, sensitive, or proprietary information unless they understand and accept the applicable third-party processing practices.</p>
      <p>Relevant third-party policies include:</p>
      <ul>
        <li><a href="https://openrouter.ai/privacy" target="_blank" rel="noopener">OpenRouter Privacy Policy</a></li>
        <li><a href="https://openrouter.ai/terms" target="_blank" rel="noopener">OpenRouter Terms of Service</a></li>
      </ul>
      <p>Additional terms may apply to the specific AI model provider selected.</p>

      <h2>5. Local Sprite Processing</h2>
      <p>After an AI-generated redraw has been received, certain sprite-processing operations are performed locally.</p>
      <p>The <strong>Update Sprite</strong> feature reuses the previously generated redraw stored on the user’s device.</p>
      <p>Under the current implementation, this operation does not submit another AI generation request or retransmit the image to OpenRouter.</p>
      <p>Updating one sprite, or the finished sprites in a batch, does not resend those images and does not resend the rest of the batch.</p>
      <p>This distinction applies specifically to the Update Sprite operation and does not imply that every Service feature operates without network communication.</p>

      <h2>6. Payments and Downloads</h2>
      <p>Kaldr Studio offers downloadable sprite packages through a Pay What You Want (“PWYW”) pricing model.</p>
      <p>Users may select an available contribution amount, including $0 where offered.</p>
      <p>For a batch, the offered amounts follow the count of successfully rendered sprites in the package, and the package contains only those sprites.</p>
      <h3>6.1 Payment Processing</h3>
      <p>Paid contributions are processed by Stripe, an independent third-party payment processor.</p>
      <p>When a user selects a paid contribution, Stripe may collect and process information necessary to complete the transaction, including:</p>
      <ul>
        <li>Payment card or other payment method information.</li>
        <li>Billing information and email addresses, where required.</li>
        <li>Transaction amounts, payment status, and payment metadata.</li>
        <li>Information necessary for fraud prevention, payment security, and regulatory compliance.</li>
      </ul>
      <p>Kaldr Studio does not directly collect or store complete payment card numbers or card security codes.</p>
      <p>Depending on the payment integration, Kaldr Studio may receive limited transaction information from Stripe, including transaction identifiers, payment amounts, payment status, and customer contact information.</p>
      <p>Stripe processes payment information under its own privacy and security practices.</p>
      <p>For additional information, review the <a href="https://stripe.com/privacy" target="_blank" rel="noopener">Stripe Privacy Policy</a>.</p>
      <h3>6.2 Free Downloads</h3>
      <p>Where a $0 contribution is available, users may download eligible assets without providing payment card information.</p>
      <p>Free downloads do not require payment processing.</p>
      <h3>6.3 Downloaded Files</h3>
      <p>Following the applicable checkout or download process, users may export generated sprite assets as ZIP packages.</p>
      <p>Downloaded files are saved to the user’s device and are subject to its local storage, backup, and security settings.</p>
      <p>Kaldr Studio does not guarantee the continued availability or recoverability of downloaded files.</p>

      <h2>7. Data Sharing and Sale</h2>
      <p>Kaldr Studio does not sell user images, prompts, generated sprites, or API credentials.</p>
      <p>Information may be transmitted to third-party service providers where necessary to perform user-requested functionality.</p>
      <p>These providers include:</p>
      <ul>
        <li><strong>OpenRouter and selected AI model providers:</strong> To process generation requests and validate API credentials.</li>
        <li><strong>Stripe:</strong> To process paid contributions, facilitate transactions, and perform associated payment operations.</li>
      </ul>
      <p>Kaldr Studio does not intentionally transmit user project files to unrelated third parties for advertising or marketing purposes.</p>
      <p>This statement does not cover information independently collected by operating systems, backup providers, payment processors, AI providers, or other services outside Kaldr Studio’s control.</p>

      <h2>8. Data Retention and Deletion</h2>
      <p>Project files and application data may remain on the local device until removed by the user or by applicable application or operating system processes.</p>
      <p>Uninstalling the application may not automatically remove all project files, configuration files, or locally stored API credentials.</p>
      <p>Users are responsible for identifying and deleting locally stored information they no longer wish to retain.</p>
      <p>Information transmitted to OpenRouter, AI model providers, or Stripe may remain subject to those providers’ independent retention and deletion policies.</p>
      <p>Deleting local files does not necessarily delete information previously transmitted to third parties.</p>
      <p>Kaldr Studio may retain transaction records where necessary for accounting, fraud prevention, dispute resolution, or compliance with applicable legal obligations.</p>

      <h2>9. Information Security</h2>
      <p>Kaldr Studio uses local storage practices and file permissions intended to reduce unnecessary exposure of user data and API credentials.</p>
      <p>However, no software, storage mechanism, network transmission, or third-party service can be guaranteed completely secure.</p>
      <p><strong>Kaldr Studio does not guarantee that the Service is immune from unauthorized access, data loss, credential compromise, malware, software vulnerabilities, or other security incidents.</strong></p>
      <p>Users should avoid submitting information that requires a level of confidentiality or protection the Service cannot provide.</p>

      <h2>10. Children’s Privacy</h2>
      <p>Kaldr Studio is not specifically directed toward children under the age of 13.</p>
      <p>The Service does not knowingly request personal information from children under 13.</p>
      <p>If we become aware that personal information from a child has been collected in violation of applicable law, we will take appropriate steps consistent with our legal obligations and technical capabilities.</p>
      <p>Users should not submit images or other materials containing children’s personal information without appropriate authorization.</p>

      <h2>11. International Data Processing</h2>
      <p>Third-party AI and payment services may process information in jurisdictions outside the user’s country or region.</p>
      <p>These jurisdictions may provide different legal protections for personal information.</p>
      <p>Kaldr Studio does not control the geographic locations in which OpenRouter, its model providers, or Stripe process submitted information.</p>
      <p>Where applicable law requires additional protections for international transfers, those requirements will apply.</p>

      <h2>12. Your Privacy Rights</h2>
      <p>Depending on your location and applicable law, you may have rights concerning personal information, including rights to access, correct, delete, or obtain information about certain processing activities.</p>
      <p>Because much of Kaldr Studio’s project data is stored locally, users may be able to manage or delete that information directly on their devices.</p>
      <p>Requests involving information independently controlled by OpenRouter, Stripe, or other third-party providers may need to be directed to those providers.</p>
      <p>Kaldr Studio will respond to applicable privacy requests in accordance with its legal obligations and technical capabilities.</p>

      <h2>13. Changes to This Privacy Policy</h2>
      <p>Kaldr Studio may update this Privacy Policy to reflect changes in application functionality, data practices, third-party integrations, or applicable legal requirements.</p>
      <p>Updates will be reflected by revising the “Last Updated” date at the beginning of this document.</p>
      <p>Where applicable law requires additional notice or consent for material changes, we will comply with those requirements.</p>

      <h2>14. Limitations of This Policy</h2>
      <p>This Privacy Policy describes Kaldr Studio’s intended data-handling practices.</p>
      <p>It does not constitute a guarantee of anonymity, confidentiality, data security, or uninterrupted availability.</p>
      <p>Nothing in this Privacy Policy excludes or limits rights or obligations that cannot lawfully be excluded or limited.</p>

      <h2>15. Contact</h2>
      <p>For questions, concerns, or requests relating to this Privacy Policy, contact Kaldr Industries LLC using the contact information published on the Service’s official website.</p>

      <div className="close">
        <p><strong>Kaldr Studio</strong></p>
        <p className="tagline">Create. Animate. Export.</p>
      </div>
    </Page>
  )
}
