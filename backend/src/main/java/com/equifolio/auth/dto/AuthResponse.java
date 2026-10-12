package com.equifolio.auth.dto;

import com.equifolio.profile.User;

public record AuthResponse(
        String token,
        String tokenType,
        Long id,
        String username,
        String email,
        Integer riskScore,
        String riskProfile,
        String message
) {
    public static AuthResponse of(String token, User user, String message) {
        return new AuthResponse(
                token,
                "Bearer",
                user.getId(),
                user.getUsername(),
                user.getEmail(),
                user.getRiskScore(),
                user.getRiskProfile(),
                message
        );
    }
}
