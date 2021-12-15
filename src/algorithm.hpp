#ifndef ASIC_ALGORITHM_HPP
#define ASIC_ALGORITHM_HPP

#include <cstddef>
#include <iterator>
#include <memory>
#include <type_traits>
#include <utility>

namespace asic {
namespace detail {

template <typename Reference>
class arrow_proxy final {
public:
	template <typename Ref>
	constexpr explicit arrow_proxy(Ref&& r)
		: m_r(std::forward<Ref>(r)) {}

	Reference* operator->() {
		return std::addressof(m_r);
	}

private:
	Reference m_r;
};

template <typename T>
class range_view final {
public:
	class iterator final {
	public:
		using difference_type = std::ptrdiff_t;
		using value_type = T const;
		using reference = value_type&;
		using pointer = value_type*;
		using iterator_category = std::random_access_iterator_tag;

		constexpr iterator() noexcept = default;
		constexpr explicit iterator(T value) noexcept
			: m_value(value) {}

		[[nodiscard]] constexpr bool operator==(iterator const& other) const noexcept {
			return m_value == other.m_value;
		}

		[[nodiscard]] constexpr bool operator!=(iterator const& other) const noexcept {
			return m_value != other.m_value;
		}

		[[nodiscard]] constexpr bool operator<(iterator const& other) const noexcept {
			return m_value < other.m_value;
		}

		[[nodiscard]] constexpr bool operator>(iterator const& other) const noexcept {
			return m_value > other.m_value;
		}

		[[nodiscard]] constexpr bool operator<=(iterator const& other) const noexcept {
			return m_value <= other.m_value;
		}

		[[nodiscard]] constexpr bool operator>=(iterator const& other) const noexcept {
			return m_value >= other.m_value;
		}

		[[nodiscard]] constexpr reference operator*() const noexcept {
			return m_value;
		}

		[[nodiscard]] constexpr pointer operator->() const noexcept {
			return std::addressof(**this);
		}

		constexpr iterator& operator++() noexcept {
			++m_value;
			return *this;
		}

		constexpr iterator operator++(int) noexcept {
			return iterator{m_value++};
		}

		constexpr iterator& operator--() noexcept {
			--m_value;
			return *this;
		}

		constexpr iterator operator--(int) noexcept {
			return iterator{m_value--};
		}

		constexpr iterator& operator+=(difference_type n) noexcept {
			m_value += n;
			return *this;
		}

		constexpr iterator& operator-=(difference_type n) noexcept {
			m_value -= n;
			return *this;
		}

		[[nodiscard]] constexpr T operator[](difference_type n) noexcept {
			return m_value + static_cast<T>(n);
		}

		[[nodiscard]] constexpr friend iterator operator+(iterator const& lhs, difference_type rhs) noexcept {
			return iterator{lhs.m_value + rhs};
		}

		[[nodiscard]] constexpr friend iterator operator+(difference_type lhs, iterator const& rhs) noexcept {
			return iterator{lhs + rhs.m_value};
		}

		[[nodiscard]] constexpr friend iterator operator-(iterator const& lhs, difference_type rhs) noexcept {
			return iterator{lhs.m_value - rhs};
		}

		[[nodiscard]] constexpr friend difference_type operator-(iterator const& lhs, iterator const& rhs) noexcept {
			return static_cast<difference_type>(lhs.m_value - rhs.m_value);
		}

	private:
		T m_value{};
	};

	using sentinel = iterator;

	template <typename First, typename Last>
	constexpr range_view(First&& first, Last&& last) noexcept
		: m_begin(std::forward<First>(first))
		, m_end(std::forward<Last>(last)) {}

	[[nodiscard]] constexpr iterator begin() const noexcept {
		return m_begin;
	}

	[[nodiscard]] constexpr sentinel end() const noexcept {
		return m_end;
	}

private:
	iterator m_begin;
	sentinel m_end;
};

template <typename Range, typename Iterator, typename Sentinel>
class enumerate_view final {
public:
	using sentinel = Sentinel;

	class iterator final {
	public:
		using difference_type = typename std::iterator_traits<Iterator>::difference_type;
		using value_type = typename std::iterator_traits<Iterator>::value_type;
		using reference = std::pair<std::size_t const&, decltype(*std::declval<Iterator const>())>;
		using pointer = arrow_proxy<reference>;
		using iterator_category =
			std::common_type_t<typename std::iterator_traits<Iterator>::iterator_category, std::bidirectional_iterator_tag>;

		constexpr iterator() = default;

		constexpr iterator(Iterator it, std::size_t index)
			: m_it(std::move(it))
			, m_index(index) {}

		[[nodiscard]] constexpr bool operator==(iterator const& other) const {
			return m_it == other.m_it;
		}

		[[nodiscard]] constexpr bool operator!=(iterator const& other) const {
			return m_it != other.m_it;
		}

		[[nodiscard]] constexpr bool operator==(sentinel const& other) const {
			return m_it == other;
		}

		[[nodiscard]] constexpr bool operator!=(sentinel const& other) const {
			return m_it != other;
		}

		[[nodiscard]] constexpr reference operator*() const {
			return reference{m_index, *m_it};
		}

		[[nodiscard]] constexpr pointer operator->() const {
			return pointer{**this};
		}

		constexpr iterator& operator++() {
			++m_it;
			++m_index;
			return *this;
		}

		constexpr iterator operator++(int) {
			return iterator{m_it++, m_index++};
		}

		constexpr iterator& operator--() {
			--m_it;
			--m_index;
			return *this;
		}

		constexpr iterator operator--(int) {
			return iterator{m_it--, m_index--};
		}

	private:
		Iterator m_it;
		std::size_t m_index = 0;
	};

	template <typename R>
	constexpr explicit enumerate_view(R&& range)
		: m_range(std::forward<R>(range)) {}

	[[nodiscard]] constexpr iterator begin() const {
		return iterator{std::begin(m_range), 0};
	}

	[[nodiscard]] constexpr sentinel end() const {
		return std::end(m_range);
	}

private:
	Range m_range;
};

template <typename Range1, typename Range2, typename Iterator1, typename Iterator2, typename Sentinel1, typename Sentinel2>
class zip_view final {
public:
	using sentinel = std::pair<Sentinel1, Sentinel2>;

	class iterator final {
	public:
		using difference_type = std::common_type_t<typename std::iterator_traits<Iterator1>::difference_type,
												   typename std::iterator_traits<Iterator2>::difference_type>;
		using value_type =
			std::pair<typename std::iterator_traits<Iterator1>::value_type, typename std::iterator_traits<Iterator2>::value_type>;
		using reference = std::pair<decltype(*std::declval<Iterator1 const>()), decltype(*std::declval<Iterator2 const>())>;
		using pointer = arrow_proxy<reference>;
		using iterator_category =
			std::common_type_t<typename std::iterator_traits<Iterator1>::iterator_category,
							   typename std::iterator_traits<Iterator2>::iterator_category, std::bidirectional_iterator_tag>;

		constexpr iterator() = default;

		constexpr iterator(Iterator1 it1, Iterator2 it2)
			: m_it1(std::move(it1))
			, m_it2(std::move(it2)) {}

		[[nodiscard]] constexpr bool operator==(iterator const& other) const {
			return m_it1 == other.m_it1 && m_it2 == other.m_it2;
		}

		[[nodiscard]] constexpr bool operator!=(iterator const& other) const {
			return !(*this == other);
		}

		[[nodiscard]] constexpr bool operator==(sentinel const& other) const {
			return m_it1 == other.first || m_it2 == other.second;
		}

		[[nodiscard]] constexpr bool operator!=(sentinel const& other) const {
			return !(*this == other);
		}

		[[nodiscard]] constexpr reference operator*() const {
			return reference{*m_it1, *m_it2};
		}

		[[nodiscard]] constexpr pointer operator->() const {
			return pointer{**this};
		}

		constexpr iterator& operator++() {
			++m_it1;
			++m_it2;
			return *this;
		}

		constexpr iterator operator++(int) {
			return iterator{m_it1++, m_it2++};
		}

		constexpr iterator& operator--() {
			--m_it1;
			--m_it2;
			return *this;
		}

		constexpr iterator operator--(int) {
			return iterator{m_it1--, m_it2--};
		}

	private:
		Iterator1 m_it1;
		Iterator2 m_it2;
	};

	template <typename R1, typename R2>
	constexpr zip_view(R1&& range1, R2&& range2)
		: m_range1(std::forward<R1>(range1))
		, m_range2(std::forward<R2>(range2)) {}

	[[nodiscard]] constexpr iterator begin() const {
		return iterator{std::begin(m_range1), std::begin(m_range2)};
	}

	[[nodiscard]] constexpr sentinel end() const {
		return sentinel{std::end(m_range1), std::end(m_range2)};
	}

private:
	Range1 m_range1;
	Range2 m_range2;
};

} // namespace detail

template <typename First, typename Last, typename T = std::remove_cv_t<std::remove_reference_t<First>>>
[[nodiscard]] constexpr auto range(First&& first, Last&& last) {
	return detail::range_view<T>{std::forward<First>(first), std::forward<Last>(last)};
}

template <typename Last, typename T = std::remove_cv_t<std::remove_reference_t<Last>>>
[[nodiscard]] constexpr auto range(Last&& last) {
	return detail::range_view<T>{T{}, std::forward<Last>(last)};
}

template <typename Range, typename Iterator = decltype(std::begin(std::declval<Range>())),
		  typename Sentinel = decltype(std::end(std::declval<Range>()))>
[[nodiscard]] constexpr auto enumerate(Range&& range) {
	return detail::enumerate_view<Range, Iterator, Sentinel>{std::forward<Range>(range)};
}

template <typename Range1, typename Range2, typename Iterator1 = decltype(std::begin(std::declval<Range1>())),
		  typename Iterator2 = decltype(std::begin(std::declval<Range2>())),
		  typename Sentinel1 = decltype(std::end(std::declval<Range1>())), typename Sentinel2 = decltype(std::end(std::declval<Range2>()))>
[[nodiscard]] constexpr auto zip(Range1&& range1, Range2&& range2) {
	return detail::zip_view<Range1, Range2, Iterator1, Iterator2, Sentinel1, Sentinel2>{std::forward<Range1>(range1),
																						std::forward<Range2>(range2)};
}

} // namespace asic

#endif // ASIC_ALGORITHM_HPP
