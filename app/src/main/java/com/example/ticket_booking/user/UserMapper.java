package com.example.ticket_booking.user;

import org.apache.ibatis.annotations.*;

@Mapper
public interface UserMapper {

    @Select("""
        SELECT id, username, password_hash AS passwordHash, role
        FROM users
        WHERE username = #{username}
        """)
    LoginAccount findByUsername(@Param("username") String username);

    @Insert("""
            INSERT INTO users (username, password_hash, role)
            VALUES (#{username}, #{passwordHash}, 'USER')
            """)
    @Options(useGeneratedKeys = true, keyProperty = "id")
    int insert(UserAccount account);
}