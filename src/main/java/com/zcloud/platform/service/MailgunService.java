package com.zcloud.platform.service;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.*;
import org.springframework.stereotype.Service;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.client.RestTemplate;

import java.util.Base64;

@Service
public class MailgunService {

    private static final Logger log = LoggerFactory.getLogger(MailgunService.class);

    @Value("${mailgun.api-key}")
    private String apiKey;

    @Value("${mailgun.domain}")
    private String domain;

    @Autowired
    private RestTemplate restTemplate;

    public void sendOtp(String toEmail, String otpCode) {
        String url = "https://api.mailgun.net/v3/" + domain + "/messages";

        String credentials = "api:" + apiKey;
        String encodedCredentials = Base64.getEncoder()
                .encodeToString(credentials.getBytes());

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.MULTIPART_FORM_DATA);
        headers.set("Authorization", "Basic " + encodedCredentials);

        MultiValueMap<String, String> body = new LinkedMultiValueMap<>();
        body.add("from", "HomeLend Pro <noreply@" + domain + ">");
        body.add("to", toEmail);
        body.add("subject", "Your HomeLend Pro login code");
        body.add("text",
                "Your one-time login code is: " + otpCode + "\n\n" +
                "This code expires in 10 minutes.\n" +
                "If you did not request this code, you can safely ignore this email.");
        body.add("html",
                "<div style=\"font-family: 'Inter', Arial, sans-serif; max-width: 400px; margin: 0 auto; text-align: center; padding: 40px 20px; background: #f9fafb; border-radius: 16px;\">" +
                "<div style=\"width: 48px; height: 48px; background: #2563eb; border-radius: 12px; margin: 0 auto 16px; line-height: 48px; color: white; font-size: 18px; font-weight: bold;\">HL</div>" +
                "<h2 style=\"color: #111827; margin-bottom: 8px;\">Your login code</h2>" +
                "<p style=\"color: #6b7280; font-size: 14px; margin-bottom: 24px;\">Enter this code to sign in to HomeLend Pro</p>" +
                "<p style=\"font-size: 36px; font-weight: bold; color: #2563eb; letter-spacing: 8px; margin: 24px 0;\">" + otpCode + "</p>" +
                "<p style=\"color: #6b7280; font-size: 13px; margin-top: 24px;\">This code expires in 10 minutes.</p>" +
                "</div>");

        HttpEntity<MultiValueMap<String, String>> request = new HttpEntity<>(body, headers);

        try {
            ResponseEntity<String> response = restTemplate.postForEntity(url, request, String.class);
            if (response.getStatusCode().is2xxSuccessful()) {
                log.info("OTP email sent to {}", toEmail);
            } else {
                log.error("Mailgun returned status {} for {}", response.getStatusCode(), toEmail);
                throw new RuntimeException("Failed to send OTP email");
            }
        } catch (Exception e) {
            log.error("Error sending OTP email to {}: {}", toEmail, e.getMessage());
            throw new RuntimeException("Failed to send OTP email: " + e.getMessage());
        }
    }
}
