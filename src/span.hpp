#ifndef ASIC_SPAN_HPP
#define ASIC_SPAN_HPP

#include <algorithm>
#include <array>
#include <cassert>
#include <cstddef>
#include <iterator>
#include <limits>
#include <type_traits>
#include <utility>

namespace asic {

constexpr auto dynamic_size = static_cast<std::size_t>(-1);

// C++17-compatible std::span substitute.
template <typename T, std::size_t Size = dynamic_size>
class span;

namespace detail {

template <typename T>
struct is_span_impl : std::false_type {};

template <typename T, std::size_t Size>
struct is_span_impl<span<T, Size>> : std::true_type {};

template <typename T>
struct is_span : is_span_impl<std::remove_cv_t<T>> {};

template <typename T>
constexpr auto is_span_v = is_span<T>::value;

template <typename T>
struct is_std_array_impl : std::false_type {};

template <typename T, std::size_t Size>
struct is_std_array_impl<std::array<T, Size>> : std::true_type {};

template <typename T>
struct is_std_array : is_std_array_impl<std::remove_cv_t<T>> {};

template <typename T>
constexpr auto is_std_array_v = is_std_array<T>::value;

template <std::size_t From, std::size_t To>
struct is_size_convertible : std::bool_constant<From == To || From == dynamic_size || To == dynamic_size> {};

template <std::size_t From, std::size_t To>
constexpr auto is_size_convertible_v = is_size_convertible<From, To>::value;

template <typename From, typename To>
struct is_element_type_convertible : std::bool_constant<std::is_convertible_v<From (*)[], To (*)[]>> {};

template <typename From, typename To>
constexpr auto is_element_type_convertible_v = is_element_type_convertible<From, To>::value;

template <typename T, std::size_t Size>
struct span_base {
	using element_type = T;
	using pointer = element_type*;
	using size_type = std::size_t;

	constexpr span_base() noexcept = default;

	constexpr span_base(pointer data, [[maybe_unused]] size_type size)
		: m_data(data) {
		assert(size == Size);
	}

	template <size_type N>
	constexpr span_base(span_base<T, N> other)
		: m_data(other.data()) {
		static_assert(N == Size || N == dynamic_size);
		assert(other.size() == Size);
	}

	[[nodiscard]] constexpr pointer data() const noexcept {
		return m_data;
	}

	[[nodiscard]] constexpr size_type size() const noexcept {
		return Size;
	}

private:
	pointer m_data = nullptr;
};

template <typename T>
struct span_base<T, dynamic_size> {
	using element_type = T;
	using pointer = element_type*;
	using size_type = std::size_t;

	constexpr span_base() noexcept = default;

	constexpr span_base(pointer data, size_type size)
		: m_data(data)
		, m_size(size) {}

	template <size_type N>
	explicit constexpr span_base(span_base<T, N> other)
		: m_data(other.data())
		, m_size(other.size()) {}

	[[nodiscard]] constexpr pointer data() const noexcept {
		return m_data;
	}

	[[nodiscard]] constexpr size_type size() const noexcept {
		return m_size;
	}

private:
	pointer m_data = nullptr;
	size_type m_size = 0;
};

template <typename T, std::size_t Size, std::size_t Offset, std::size_t N>
struct subspan_type {
	using type = span<T, (N != dynamic_size) ? N : (Size != dynamic_size) ? Size - Offset : Size>;
};

template <typename T, std::size_t Size, std::size_t Offset, std::size_t Count>
using subspan_type_t = typename subspan_type<T, Size, Offset, Count>::type;

} // namespace detail

template <typename T, std::size_t Size>
class span final : public detail::span_base<T, Size> { // NOLINT(cppcoreguidelines-special-member-functions)
public:
	using element_type = typename detail::span_base<T, Size>::element_type;
	using pointer = typename detail::span_base<T, Size>::pointer;
	using size_type = typename detail::span_base<T, Size>::size_type;
	using value_type = std::remove_cv_t<element_type>;
	using reference = element_type&;
	using iterator = element_type*;
	using const_iterator = const element_type*;
	using reverse_iterator = std::reverse_iterator<iterator>;
	using const_reverse_iterator = std::reverse_iterator<const_iterator>;

	// Default constructor.
	constexpr span() noexcept = default;

	// Construct from pointer, size.
	constexpr span(pointer data, size_type size)
		: detail::span_base<T, Size>(data, size) {}

	// Copy constructor.
	template <typename U, std::size_t N, typename = std::enable_if_t<detail::is_size_convertible_v<N, Size>>,
			  typename = std::enable_if_t<detail::is_element_type_convertible_v<U, T>>>
	constexpr span(span<U, N> const& other)
		: span(other.data(), other.size()) {}

	// Copy assignment.
	constexpr span& operator=(span const&) noexcept = default;

	// Destructor.
	~span() = default;

	// Construct from begin, end.
	constexpr span(pointer begin, pointer end)
		: span(begin, end - begin) {}

	// Construct from C array.
	template <std::size_t N>
	constexpr span(element_type (&arr)[N]) noexcept
		: span(std::data(arr), N) {}

	// Construct from std::array.
	template <std::size_t N, typename = std::enable_if_t<N != 0>>
	constexpr span(std::array<value_type, N>& arr) noexcept
		: span(std::data(arr), N) {}

	// Construct from empty std::array.
	constexpr span(std::array<value_type, 0>&) noexcept
		: span() {}

	// Construct from const std::array.
	template <std::size_t N, typename = std::enable_if_t<N != 0>>
	constexpr span(std::array<value_type, N> const& arr) noexcept
		: span(std::data(arr), N) {}

	// Construct from empty const std::array.
	constexpr span(std::array<value_type, 0> const&) noexcept
		: span() {}

	// Construct from other container.
	template <
		typename Container, typename = std::enable_if_t<!detail::is_span_v<Container>>,
		typename = std::enable_if_t<!detail::is_std_array_v<Container>>, typename = decltype(std::data(std::declval<Container>())),
		typename = decltype(std::size(std::declval<Container>())),
		typename = std::enable_if_t<std::is_convertible_v<typename Container::pointer, pointer>>,
		typename = std::enable_if_t<std::is_convertible_v<typename Container::pointer, decltype(std::data(std::declval<Container>()))>>>
	constexpr span(Container& container)
		: span(std::data(container), std::size(container)) {}

	// Construct from other const container.
	template <
		typename Container, typename Element = element_type, typename = std::enable_if_t<std::is_const_v<Element>>,
		typename = std::enable_if_t<!detail::is_span_v<Container>>, typename = std::enable_if_t<!detail::is_std_array_v<Container>>,
		typename = decltype(std::data(std::declval<Container>())), typename = decltype(std::size(std::declval<Container>())),
		typename = std::enable_if_t<std::is_convertible_v<typename Container::pointer, pointer>>,
		typename = std::enable_if_t<std::is_convertible_v<typename Container::pointer, decltype(std::data(std::declval<Container>()))>>>
	constexpr span(Container const& container)
		: span(std::data(container), std::size(container)) {}

	[[nodiscard]] constexpr iterator begin() const noexcept {
		return this->data();
	}

	[[nodiscard]] constexpr const_iterator cbegin() const noexcept {
		return this->data();
	}

	[[nodiscard]] constexpr iterator end() const noexcept {
		return this->data() + this->size();
	}

	[[nodiscard]] constexpr const_iterator cend() const noexcept {
		return this->data() + this->size();
	}

	[[nodiscard]] constexpr reverse_iterator rbegin() const noexcept {
		return std::make_reverse_iterator(this->end());
	}

	[[nodiscard]] constexpr const_reverse_iterator crbegin() const noexcept {
		return std::make_reverse_iterator(this->cend());
	}

	[[nodiscard]] constexpr reverse_iterator rend() const noexcept {
		return std::make_reverse_iterator(this->begin());
	}

	[[nodiscard]] constexpr const_reverse_iterator crend() const noexcept {
		return std::make_reverse_iterator(this->cbegin());
	}

	[[nodiscard]] constexpr reference operator[](size_type i) const noexcept {
		assert(i < this->size());
		return this->data()[i];
	}

	[[nodiscard]] constexpr reference operator()(size_type i) const noexcept {
		assert(i < this->size());
		return this->data()[i];
	}

	[[nodiscard]] constexpr size_type size_bytes() const noexcept {
		return this->size() * sizeof(element_type);
	}

	[[nodiscard]] constexpr bool empty() const noexcept {
		return this->size() == 0;
	}

	[[nodiscard]] constexpr reference front() const noexcept {
		assert(!this->empty());
		return this->data()[0];
	}

	[[nodiscard]] constexpr reference back() const noexcept {
		assert(!this->empty());
		return this->data()[this->size() - 1];
	}

	template <std::size_t N>
	[[nodiscard]] constexpr span<T, N> first() const {
		static_assert(N != dynamic_size && N <= Size);
		return {this->data(), N};
	}

	template <std::size_t N>
	[[nodiscard]] constexpr span<T, N> last() const {
		static_assert(N != dynamic_size && N <= Size);
		return {this->data() + (Size - N), N};
	}

	template <std::size_t Offset, std::size_t N = dynamic_size>
	[[nodiscard]] constexpr auto subspan() const -> detail::subspan_type_t<T, Size, Offset, N> {
		static_assert(Offset <= Size);
		return {this->data() + Offset, (N == dynamic_size) ? this->size() - Offset : N};
	}

	[[nodiscard]] constexpr span<T, dynamic_size> first(size_type n) const {
		assert(n <= this->size());
		return {this->data(), n};
	}

	[[nodiscard]] constexpr span<T, dynamic_size> last(size_type n) const {
		return this->subspan(this->size() - n);
	}

	[[nodiscard]] constexpr span<T, dynamic_size> subspan(size_type offset, size_type n = dynamic_size) const {
		if constexpr (Size == dynamic_size) {
			assert(offset <= this->size());
			if (n == dynamic_size) {
				return {this->data() + offset, this->size() - offset};
			}
			assert(n <= this->size());
			assert(offset + n <= this->size());
			return {this->data() + offset, n};
		} else {
			return span<T, dynamic_size>{*this}.subspan(offset, n);
		}
	}
};

template <typename T, std::size_t LhsSize, std::size_t RhsSize>
[[nodiscard]] constexpr bool operator==(span<T, LhsSize> lhs, span<T, RhsSize> rhs) {
	return std::equal(lhs.begin(), lhs.end(), rhs.begin(), rhs.end());
}

template <typename T, std::size_t LhsSize, std::size_t RhsSize>
[[nodiscard]] constexpr bool operator!=(span<T, LhsSize> lhs, span<T, RhsSize> rhs) {
	return !(lhs == rhs);
}

template <typename T, std::size_t LhsSize, std::size_t RhsSize>
[[nodiscard]] constexpr bool operator<(span<T, LhsSize> lhs, span<T, RhsSize> rhs) {
	return std::lexicographical_compare(lhs.begin(), lhs.end(), rhs.begin(), rhs.end());
}

template <typename T, std::size_t LhsSize, std::size_t RhsSize>
[[nodiscard]] constexpr bool operator<=(span<T, LhsSize> lhs, span<T, RhsSize> rhs) {
	return !(lhs > rhs);
}

template <typename T, std::size_t LhsSize, std::size_t RhsSize>
[[nodiscard]] constexpr bool operator>(span<T, LhsSize> lhs, span<T, RhsSize> rhs) {
	return rhs < lhs;
}

template <typename T, std::size_t LhsSize, std::size_t RhsSize>
[[nodiscard]] constexpr bool operator>=(span<T, LhsSize> lhs, span<T, RhsSize> rhs) {
	return !(lhs < rhs);
}

template <typename Container>
span(Container&) -> span<typename Container::value_type>;

template <typename Container>
span(Container const&) -> span<typename Container::value_type const>;

template <typename T, std::size_t N>
span(T (&)[N]) -> span<T, N>;

template <typename T, std::size_t N>
span(std::array<T, N>&) -> span<T, N>;

template <typename T, std::size_t N>
span(std::array<T, N> const&) -> span<T const, N>;

template <typename T, typename Dummy>
span(T, Dummy &&) -> span<std::remove_reference_t<decltype(std::declval<T>()[0])>>;

} // namespace asic

#endif // ASIC_SPAN_HPP
