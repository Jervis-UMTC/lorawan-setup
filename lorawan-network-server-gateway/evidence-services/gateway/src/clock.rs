#[cfg(any(feature = "concentratord-zmq", test))]
use std::time::{SystemTime, UNIX_EPOCH};

use crate::{Error, Result};

const MILLIS_PER_SECOND: i64 = 1_000;
const SECONDS_PER_DAY: i64 = 86_400;

#[cfg(any(feature = "concentratord-zmq", test))]
pub fn utc_now_millis() -> Result<String> {
    let duration = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_err(|_| Error::Invalid("system clock is before Unix epoch"))?;
    let seconds = i64::try_from(duration.as_secs())
        .map_err(|_| Error::Invalid("system clock exceeds supported range"))?;
    format_epoch_millis(seconds, duration.subsec_millis())
}

pub fn parse_utc_millis(value: &str) -> Result<i64> {
    crate::contract::validate_utc_millis(value)?;
    let year = parse(value, 0, 4)? as i64;
    let month = parse(value, 5, 7)? as i64;
    let day = parse(value, 8, 10)? as i64;
    let hour = parse(value, 11, 13)? as i64;
    let minute = parse(value, 14, 16)? as i64;
    let second = parse(value, 17, 19)? as i64;
    let millis = parse(value, 20, 23)? as i64;
    let days = days_from_civil(year, month, day);
    days.checked_mul(SECONDS_PER_DAY)
        .and_then(|v| v.checked_add(hour * 3_600 + minute * 60 + second))
        .and_then(|v| v.checked_mul(MILLIS_PER_SECOND))
        .and_then(|v| v.checked_add(millis))
        .ok_or(Error::Invalid("timestamp exceeds supported range"))
}

#[cfg(any(feature = "concentratord-zmq", test))]
fn format_epoch_millis(seconds: i64, millis: u32) -> Result<String> {
    if seconds < 0 || millis > 999 {
        return Err(Error::Invalid("system clock outside supported range"));
    }
    let days = seconds / SECONDS_PER_DAY;
    let day_seconds = seconds % SECONDS_PER_DAY;
    let (year, month, day) = civil_from_days(days);
    if !(1..=9_999).contains(&year) {
        return Err(Error::Invalid("system clock year outside supported range"));
    }
    let hour = day_seconds / 3_600;
    let minute = (day_seconds % 3_600) / 60;
    let second = day_seconds % 60;
    Ok(format!(
        "{year:04}-{month:02}-{day:02}T{hour:02}:{minute:02}:{second:02}.{millis:03}Z"
    ))
}

fn parse(value: &str, start: usize, end: usize) -> Result<u32> {
    value[start..end]
        .parse::<u32>()
        .map_err(|_| Error::Invalid("timestamp component is invalid"))
}

// Howard Hinnant's proleptic Gregorian civil-date algorithms, expressed with
// safe integer arithmetic. Epoch day 0 is 1970-01-01.
fn days_from_civil(year: i64, month: i64, day: i64) -> i64 {
    let year = year - i64::from(month <= 2);
    let era = if year >= 0 { year } else { year - 399 } / 400;
    let yoe = year - era * 400;
    let adjusted_month = month + if month > 2 { -3 } else { 9 };
    let doy = (153 * adjusted_month + 2) / 5 + day - 1;
    let doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
    era * 146_097 + doe - 719_468
}

#[cfg(any(feature = "concentratord-zmq", test))]
fn civil_from_days(days: i64) -> (i64, i64, i64) {
    let z = days + 719_468;
    let era = if z >= 0 { z } else { z - 146_096 } / 146_097;
    let doe = z - era * 146_097;
    let yoe = (doe - doe / 1_460 + doe / 36_524 - doe / 146_096) / 365;
    let mut year = yoe + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let day = doy - (153 * mp + 2) / 5 + 1;
    let month = mp + if mp < 10 { 3 } else { -9 };
    year += i64::from(month <= 2);
    (year, month, day)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn current_utc_value_matches_the_millisecond_contract() {
        let now = utc_now_millis().unwrap();
        assert!(parse_utc_millis(&now).unwrap() > 0);
    }

    #[test]
    fn epoch_and_leap_day_round_trip() {
        assert_eq!(parse_utc_millis("1970-01-01T00:00:00.000Z").unwrap(), 0);
        let leap = parse_utc_millis("2024-02-29T12:34:56.789Z").unwrap();
        assert_eq!(leap, 1_709_210_096_789);
        assert_eq!(
            format_epoch_millis(leap / 1_000, (leap % 1_000) as u32).unwrap(),
            "2024-02-29T12:34:56.789Z"
        );
    }
}
