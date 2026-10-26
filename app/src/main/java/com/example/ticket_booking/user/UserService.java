package com.example.ticket_booking.user;

import org.springframework.dao.DuplicateKeyException;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;

@Service
public class UserService {
    private final UserMapper userMapper;
    private final PasswordEncoder passwordEncoder;

    public UserService(UserMapper userMapper, PasswordEncoder passwordEncoder) {
        this.userMapper = userMapper;
        this.passwordEncoder = passwordEncoder;
    }

    public long register(String username, String rawPassword) {
        String hash = passwordEncoder.encode(rawPassword);
        UserAccount account = new UserAccount(username, hash);

        try {
            if (userMapper.insert(account) != 1 || account.getId() == null) {
                throw new IllegalStateException("用户创建失败");
            }
        } catch (DuplicateKeyException e) {
            throw new UsernameTakenException();
        }

        return account.getId();
    }
}