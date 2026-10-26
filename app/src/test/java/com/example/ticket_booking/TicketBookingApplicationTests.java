package com.example.ticket_booking;

import java.sql.Connection;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import javax.sql.DataSource;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

@SpringBootTest
class TicketBookingApplicationTests {

	@Autowired
	private DataSource dataSource;

	@Test
	void connectsToTicketBookingDatabase() throws SQLException {
		try (Connection connection = dataSource.getConnection();
			 Statement statement = connection.createStatement();
			 ResultSet result = statement.executeQuery("SELECT DATABASE()")) {

			assertTrue(result.next());
			assertEquals("ticket_booking", result.getString(1));
		}
	}
}