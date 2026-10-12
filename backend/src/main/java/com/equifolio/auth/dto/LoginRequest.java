package com.equifolio.auth.dto;

import jakarta.validation.constraints.NotBlank;

public record LoginRequest(
        @NotBlank(message = "Tên đăng nhập hoặc Email không được để trống")
        String usernameOrEmail,

        @NotBlank(message = "Mật khẩu không được để trống")
        String password
) {}
