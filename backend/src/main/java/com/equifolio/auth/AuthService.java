package com.equifolio.auth;

import com.equifolio.auth.dto.AuthResponse;
import com.equifolio.auth.dto.LoginRequest;
import com.equifolio.auth.dto.RegisterRequest;
import com.equifolio.ledger.Account;
import com.equifolio.ledger.AccountRepository;
import com.equifolio.market.Asset;
import com.equifolio.market.AssetRepository;
import com.equifolio.profile.PortfolioTarget;
import com.equifolio.profile.PortfolioTargetRepository;
import com.equifolio.profile.User;
import com.equifolio.profile.UserRepository;
import org.springframework.security.authentication.BadCredentialsException;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.time.Instant;

@Service
public class AuthService {

    private final UserRepository userRepository;
    private final PortfolioTargetRepository portfolioTargetRepository;
    private final AccountRepository accountRepository;
    private final AssetRepository assetRepository;
    private final PasswordEncoder passwordEncoder;
    private final JwtTokenProvider tokenProvider;

    public AuthService(UserRepository userRepository,
                       PortfolioTargetRepository portfolioTargetRepository,
                       AccountRepository accountRepository,
                       AssetRepository assetRepository,
                       PasswordEncoder passwordEncoder,
                       JwtTokenProvider tokenProvider) {
        this.userRepository = userRepository;
        this.portfolioTargetRepository = portfolioTargetRepository;
        this.accountRepository = accountRepository;
        this.assetRepository = assetRepository;
        this.passwordEncoder = passwordEncoder;
        this.tokenProvider = tokenProvider;
    }

    @Transactional
    public AuthResponse register(RegisterRequest req) {
        String cleanUsername = req.username().trim();
        String cleanEmail = req.email().trim().toLowerCase();

        if (userRepository.existsByUsername(cleanUsername)) {
            throw new IllegalArgumentException("Tên đăng nhập '" + cleanUsername + "' đã được sử dụng");
        }
        if (userRepository.existsByEmail(cleanEmail)) {
            throw new IllegalArgumentException("Email '" + cleanEmail + "' đã được sử dụng");
        }

        User user = new User();
        user.setUsername(cleanUsername);
        user.setEmail(cleanEmail);
        user.setPasswordHash(passwordEncoder.encode(req.password()));
        user.setRiskScore(50);
        user.setRiskAversionLambda(new BigDecimal("5.00"));
        user.setRiskProfile("BALANCED");
        user.setCreatedAt(Instant.now());
        User savedUser = userRepository.save(user);

        // Khởi tạo các tài khoản Sổ cái kép cơ bản
        initInitialAccounts(savedUser);

        // Khởi tạo tỷ trọng mục tiêu chiến lược SAA mặc định (35% Cổ phiếu, 35% Vàng, 30% Tiết kiệm/Tiền mặt)
        initInitialPortfolioTargets(savedUser);

        String token = tokenProvider.generateToken(savedUser.getId(), savedUser.getUsername());
        return AuthResponse.of(token, savedUser, "Đăng ký tài khoản thành công! Chào mừng đến với EquiFolio.");
    }

    @Transactional
    public AuthResponse login(LoginRequest req) {
        String identifier = req.usernameOrEmail().trim();
        User user = userRepository.findByUsername(identifier)
                .or(() -> userRepository.findByEmail(identifier.toLowerCase()))
                .orElseThrow(() -> new BadCredentialsException("Tên đăng nhập hoặc mật khẩu không chính xác"));

        boolean matches = passwordEncoder.matches(req.password(), user.getPasswordHash());

        // Hỗ trợ đăng nhập nhanh cho Demo User 'alex_nguyen' với mật khẩu '123456' hoặc 'password123'
        if (!matches && ("alex_nguyen".equals(user.getUsername()) || "alex.nguyen@equifolio.vn".equalsIgnoreCase(user.getEmail()))) {
            if ("123456".equals(req.password()) || "password123".equals(req.password())) {
                matches = true;
                user.setPasswordHash(passwordEncoder.encode(req.password()));
                userRepository.save(user);
            }
        }

        if (!matches) {
            throw new BadCredentialsException("Tên đăng nhập hoặc mật khẩu không chính xác");
        }

        String token = tokenProvider.generateToken(user.getId(), user.getUsername());
        return AuthResponse.of(token, user, "Đăng nhập thành công");
    }

    public User getCurrentUser(Long userId) {
        return userRepository.findById(userId)
                .orElseThrow(() -> new IllegalArgumentException("Không tìm thấy người dùng"));
    }

    private void initInitialAccounts(User user) {
        Asset vndAsset = assetRepository.findById("VND")
                .orElseGet(() -> assetRepository.save(new Asset("VND", "Tiền mặt Việt Nam Đồng", "CASH")));
        Asset equityAsset = assetRepository.findById("EQUITY")
                .orElseGet(() -> assetRepository.save(new Asset("EQUITY", "Tài khoản Vốn chủ sở hữu", "CASH")));

        accountRepository.save(new Account(user, "VND_WALLET", vndAsset, BigDecimal.ZERO));
        accountRepository.save(new Account(user, "EQUITY_CAPITAL", equityAsset, BigDecimal.ZERO));
    }

    private void initInitialPortfolioTargets(User user) {
        portfolioTargetRepository.save(new PortfolioTarget(user, "STOCK", new BigDecimal("0.3500")));
        portfolioTargetRepository.save(new PortfolioTarget(user, "GOLD", new BigDecimal("0.3500")));
        portfolioTargetRepository.save(new PortfolioTarget(user, "SAVINGS", new BigDecimal("0.2000")));
        portfolioTargetRepository.save(new PortfolioTarget(user, "CASH", new BigDecimal("0.1000")));
        portfolioTargetRepository.save(new PortfolioTarget(user, "CASH_SAVINGS", new BigDecimal("0.3000")));
    }
}
