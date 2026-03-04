package com.zcloud.platform.repository;

import com.zcloud.platform.model.OtpCode;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.transaction.annotation.Transactional;

import java.sql.Timestamp;
import java.time.Instant;
import java.util.Optional;
import java.util.UUID;

public interface OtpCodeRepository extends JpaRepository<OtpCode, UUID> {

    Optional<OtpCode> findTopByEmailAndCodeAndUsedFalseAndExpiresAtAfterOrderByCreatedAtDesc(
            String email, String code, Instant now);

    long countByEmailAndCreatedAtAfter(String email, Timestamp since);

    @Modifying
    @Transactional
    @Query("DELETE FROM OtpCode o WHERE o.email = :email")
    void deleteAllByEmail(@Param("email") String email);
}
