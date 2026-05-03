"""
helpers/email.py — All Transactional Email Functions
One place for every email the app sends.
"""

import base64
import logging
import resend
from config.settings import FROM_EMAIL, CONTACT_RECIPIENT

logger = logging.getLogger(__name__)


def send_otp_email(to_email: str, user_name: str, otp_code: str) -> bool:
    try:
        resend.Emails.send({
            "from":    FROM_EMAIL,
            "to":      to_email,
            "subject": "Kagazat – Password Reset OTP | पासवर्ड रीसेट OTP",
            "html": f"""
            <div style="font-family:Arial,sans-serif;max-width:480px;margin:auto;
                        border:1px solid #e5e7eb;border-radius:8px;overflow:hidden;">
              <div style="background:#2563eb;padding:24px;text-align:center;">
                <h2 style="color:#fff;margin:0;">Kagazat</h2>
              </div>
              <div style="padding:32px;">
                <p style="font-size:16px;">नमस्ते {user_name},</p>
                <p style="font-size:15px;">आपका पासवर्ड रीसेट OTP:</p>
                <div style="text-align:center;margin:24px 0;">
                  <span style="font-size:42px;font-weight:bold;letter-spacing:12px;
                               color:#2563eb;">{otp_code}</span>
                </div>
                <p style="font-size:14px;color:#6b7280;">
                  यह OTP <strong>15 मिनट</strong> के लिए वैध है।<br>
                  This OTP is valid for <strong>15 minutes</strong>.
                </p>
                <p style="font-size:13px;color:#ef4444;">
                  यदि आपने यह अनुरोध नहीं किया, तो इस ईमेल को अनदेखा करें।
                </p>
              </div>
              <div style="background:#f9fafb;padding:16px;text-align:center;
                          font-size:12px;color:#9ca3af;">
                © 2026 Kagazat. All rights reserved.
              </div>
            </div>
            """,
        })
        return True
    except Exception as e:
        logger.error("OTP email error: %s", e)
        return False


def send_pdf_email(user_email: str, pdf_bytes: bytes, filename: str) -> bool:
    """
    Accepts raw PDF bytes (not a filepath) — no disk dependency.
    """
    try:
        pdf_content = base64.b64encode(pdf_bytes).decode()
        resend.Emails.send({
            "from":    FROM_EMAIL,
            "to":      user_email,
            "subject": "आपका शपथपत्र तैयार है | Your Affidavit is Ready",
            "html": f"""
                <h2>नमस्ते!</h2>
                <p>आपका शपथपत्र तैयार है। PDF अटैचमेंट में है।</p>
                <p><strong>File:</strong> {filename}</p>
                <hr>
                <p>Your affidavit is ready. PDF attached.</p>
                <br>
                <p>धन्यवाद | Thank you<br><strong>Kagazat Team</strong></p>
            """,
            "attachments": [{"filename": filename, "content": pdf_content}],
        })
        return True
    except Exception as e:
        logger.error("PDF email error: %s", e)
        return False


def send_contact_notification(
    name: str, email: str, phone: str,
    subject: str, message: str,
    sender_ip: str, timestamp: str,
) -> bool:
    try:
        resend.Emails.send({
            "from":     FROM_EMAIL,
            "to":       CONTACT_RECIPIENT,
            "reply_to": email,
            "subject":  f"[Kagazat संपर्क] {subject} — {name}",
            "html": f"""
            <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;
                        border:1px solid #e5e7eb;border-radius:8px;overflow:hidden;">
              <div style="background:#2563eb;padding:20px 24px;">
                <h2 style="color:#fff;margin:0;font-size:18px;">
                  📬 नया संपर्क संदेश — Kagazat
                </h2>
              </div>
              <div style="padding:28px 24px;">
                <table style="width:100%;border-collapse:collapse;margin-bottom:20px;">
                  <tr style="background:#f9fafb;">
                    <td style="padding:10px 14px;font-weight:bold;width:140px;color:#374151;">नाम</td>
                    <td style="padding:10px 14px;color:#111827;">{name}</td>
                  </tr>
                  <tr>
                    <td style="padding:10px 14px;font-weight:bold;color:#374151;">ईमेल</td>
                    <td style="padding:10px 14px;">
                      <a href="mailto:{email}" style="color:#2563eb;">{email}</a>
                    </td>
                  </tr>
                  <tr style="background:#f9fafb;">
                    <td style="padding:10px 14px;font-weight:bold;color:#374151;">मोबाइल</td>
                    <td style="padding:10px 14px;color:#111827;">{phone if phone else "नहीं दिया"}</td>
                  </tr>
                  <tr>
                    <td style="padding:10px 14px;font-weight:bold;color:#374151;">विषय</td>
                    <td style="padding:10px 14px;color:#111827;">{subject}</td>
                  </tr>
                  <tr style="background:#f9fafb;">
                    <td style="padding:10px 14px;font-weight:bold;color:#374151;">समय</td>
                    <td style="padding:10px 14px;color:#111827;">{timestamp}</td>
                  </tr>
                  <tr>
                    <td style="padding:10px 14px;font-weight:bold;color:#374151;">IP</td>
                    <td style="padding:10px 14px;color:#6b7280;font-size:13px;">{sender_ip}</td>
                  </tr>
                </table>
                <div style="background:#f0f9ff;border-left:4px solid #2563eb;
                            padding:16px 20px;border-radius:4px;margin-bottom:20px;">
                  <p style="font-weight:bold;color:#1e40af;margin:0 0 8px;">संदेश:</p>
                  <p style="color:#1e293b;line-height:1.7;white-space:pre-wrap;margin:0;">{message}</p>
                </div>
                <a href="mailto:{email}?subject=Re: {subject}"
                   style="display:inline-block;background:#2563eb;color:#fff;
                          padding:12px 24px;border-radius:6px;text-decoration:none;
                          font-weight:bold;">
                  ✉️ अभी जवाब दें
                </a>
              </div>
              <div style="background:#f9fafb;padding:14px 24px;font-size:12px;color:#9ca3af;">
                यह संदेश kagazat.in के Contact Us फ़ॉर्म से आया है।
              </div>
            </div>
            """,
        })
        return True
    except Exception as e:
        logger.error("Contact notification email error: %s", e)
        return False


def send_contact_confirmation(name: str, email: str, subject: str) -> bool:
    try:
        resend.Emails.send({
            "from":    FROM_EMAIL,
            "to":      email,
            "subject": "हमने आपका संदेश प्राप्त किया | Kagazat",
            "html": f"""
            <div style="font-family:Arial,sans-serif;max-width:480px;margin:auto;
                        border:1px solid #e5e7eb;border-radius:8px;overflow:hidden;">
              <div style="background:#2563eb;padding:24px;text-align:center;">
                <h2 style="color:#fff;margin:0;">Kagazat</h2>
              </div>
              <div style="padding:32px 24px;">
                <p style="font-size:18px;font-weight:bold;color:#111827;">
                  नमस्ते {name} जी! 🙏
                </p>
                <p style="font-size:15px;color:#374151;line-height:1.7;">
                  आपका संदेश हमें मिल गया है।<br>
                  हम <strong>24 घंटे के अंदर</strong> आपको जवाब देंगे।
                </p>
                <div style="background:#f0f9ff;border:1px solid #bfdbfe;
                            padding:16px;border-radius:8px;margin:20px 0;">
                  <p style="margin:0;color:#1e40af;font-size:14px;">
                    <strong>विषय:</strong> {subject}
                  </p>
                </div>
                <p style="font-size:15px;color:#374151;line-height:1.7;">
                  यदि आपको तुरंत सहायता चाहिए:<br>
                  📧 Email: <strong>helpdesk@kagazat.in</strong>
                </p>
                <p style="font-size:15px;color:#374151;margin-top:24px;">
                  धन्यवाद<br>
                  <strong>Kagazat Team</strong>
                </p>
              </div>
              <div style="background:#f9fafb;padding:14px 24px;text-align:center;
                          font-size:12px;color:#9ca3af;">
                © 2026 Kagazat. All rights reserved. |
                <a href="https://kagazat.in" style="color:#2563eb;">kagazat.in</a>
              </div>
            </div>
            """,
        })
        return True
    except Exception as e:
        logger.error("Contact confirmation email error: %s", e)
        return False
