package com.zcloud.platform.controller;

import com.zcloud.platform.model.OtpCode;
import com.zcloud.platform.repository.OtpCodeRepository;
import com.zcloud.platform.service.MailgunService;
import com.zcloud.platform.util.JwtUtil;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.security.SecureRandom;
import java.sql.Timestamp;
import java.time.Instant;
import java.util.Map;
import java.util.Optional;

@RestController
@RequestMapping("/api/auth")
public class AuthController {

    private static final Logger log = LoggerFactory.getLogger(AuthController.class);
    private static final int OTP_EXPIRY_MINUTES = 10;
    private static final int OTP_RATE_LIMIT_PER_HOUR = 5;
    private static final SecureRandom SECURE_RANDOM = new SecureRandom();

    @Autowired
    private OtpCodeRepository otpCodeRepository;

    @Autowired
    private MailgunService mailgunService;

    @Autowired
    private JwtUtil jwtUtil;

    public record SendOtpRequest(@NotBlank @Email String email) {}
    public record VerifyOtpRequest(@NotBlank @Email String email,
                                   @NotBlank String code) {}

    @PostMapping("/send-otp")
    public ResponseEntity<?> sendOtp(@Valid @RequestBody SendOtpRequest request) {
        String email = request.email().toLowerCase().trim();

        Timestamp oneHourAgo = Timestamp.from(Instant.now().minusSeconds(3600));
        long recentCount = otpCodeRepository.countByEmailAndCreatedAtAfter(email, oneHourAgo);
        if (recentCount >= OTP_RATE_LIMIT_PER_HOUR) {
            log.warn("OTP rate limit exceeded for email: {}", email);
            return ResponseEntity.status(429)
                    .body(Map.of("error", "Too many requests. Please wait before trying again."));
        }

        String code = String.format("%06d", SECURE_RANDOM.nextInt(1_000_000));

        OtpCode otp = new OtpCode();
        otp.setEmail(email);
        otp.setCode(code);
        otp.setExpiresAt(Instant.now().plusSeconds(OTP_EXPIRY_MINUTES * 60L));
        otpCodeRepository.save(otp);

        try {
            mailgunService.sendOtp(email, code);
        } catch (Exception e) {
            log.error("Failed to send OTP to {}: {}", email, e.getMessage());
            return ResponseEntity.status(503)
                    .body(Map.of("error", "Failed to send verification email. Please try again."));
        }

        return ResponseEntity.ok(Map.of("message", "If this email is registered, a code has been sent."));
    }

    @PostMapping("/verify-otp")
    public ResponseEntity<?> verifyOtp(@Valid @RequestBody VerifyOtpRequest request) {
        String email = request.email().toLowerCase().trim();
        String code = request.code().trim();

        Optional<OtpCode> otpOpt =
                otpCodeRepository.findTopByEmailAndCodeAndUsedFalseAndExpiresAtAfterOrderByCreatedAtDesc(
                        email, code, Instant.now());

        if (otpOpt.isEmpty()) {
            return ResponseEntity.status(401)
                    .body(Map.of("error", "Invalid or expired code."));
        }

        OtpCode otp = otpOpt.get();
        otp.setUsed(true);
        otpCodeRepository.save(otp);

        String token = jwtUtil.generateToken(email);
        log.info("User authenticated via OTP: {}", email);

        return ResponseEntity.ok(Map.of(
                "token", token,
                "email", email,
                "expiresIn", 86400
        ));
    }
}
