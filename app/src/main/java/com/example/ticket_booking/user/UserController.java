package com.example.ticket_booking.user;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.web.bind.annotation.GetMapping;

@RestController
@RequestMapping("/users")
public class UserController {
    private final UserService userService;

    public UserController(UserService userService) {
        this.userService = userService;
    }

    @PostMapping("/register")
    public ResponseEntity<RegisterResponse> register(
            @Valid @RequestBody RegisterRequest request) {
        long userId = userService.register(request.username(), request.password());
        return ResponseEntity.status(HttpStatus.CREATED)
                .body(new RegisterResponse(userId));
    }

    @GetMapping("/me")
    public MeResponse me(@AuthenticationPrincipal Jwt jwt) {
        return new MeResponse(
                Long.parseLong(jwt.getSubject()),
                jwt.getClaimAsString("username"),
                jwt.getClaimAsString("role")
        );
    }

    public record MeResponse(long userId, String username, String role) {}
    public record RegisterRequest(
            @NotBlank
            @Pattern(regexp = "[A-Za-z0-9_]{3,32}")
            String username,

            @NotBlank
            @Size(min = 8, max = 64)
            String password
    ) {}

    public record RegisterResponse(long userId) {}
}